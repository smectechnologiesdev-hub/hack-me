"""
JSON API for labs (Django REST Framework).

Endpoints:
    POST /api/labs/start/                    -> create a new lab
    GET  /api/labs/<lab_token>/              -> lab detail (owner only)
    GET  /api/labs/<lab_token>/wordlist/     -> assigned wordlist (owner only)
    GET  /api/labs/<lab_token>/attempts/     -> attempt history (owner only)
    POST /api/labs/<lab_token>/login/        -> training authentication endpoint

Every per-lab endpoint enforces object-level ownership via ``get_owned_lab``.
The login endpoint is the intentionally "vulnerable" training target; all other
endpoints are ordinary authenticated reads.
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.attempts.models import Attempt
from apps.attempts.serializers import AttemptSerializer
from apps.attempts.services import Outcome, process_login_attempt

from .models import Lab
from .permissions import get_owned_lab
from .serializers import (
    LabSerializer,
    LabStartSerializer,
    TrainingLoginSerializer,
    WordlistSerializer,
)
from .services import create_lab_for_student, get_primary_lab, refresh_lab_status


class LabStartView(APIView):
    """POST /api/labs/start/ — create a fresh isolated lab for the caller."""

    throttle_scope = "lab_api"

    def post(self, request):
        in_serializer = LabStartSerializer(data=request.data)
        in_serializer.is_valid(raise_exception=True)
        difficulty = in_serializer.validated_data.get("difficulty")

        lab = create_lab_for_student(request.user, difficulty=difficulty)
        out = LabSerializer(lab, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)


class LabDetailView(APIView):
    """GET /api/labs/<lab_token>/ — lab detail for its owner."""

    throttle_scope = "lab_api"

    def get(self, request, lab_token):
        lab = get_owned_lab(request, lab_token)
        lab = refresh_lab_status(lab)
        out = LabSerializer(lab, context={"request": request})
        return Response(out.data)


class LabWordlistView(APIView):
    """GET /api/labs/<lab_token>/wordlist/ — the wordlist assigned to this lab."""

    throttle_scope = "lab_api"

    def get(self, request, lab_token):
        lab = get_owned_lab(request, lab_token)
        out = WordlistSerializer(lab.wordlist)
        return Response(out.data)


class LabAttemptsView(ListAPIView):
    """GET /api/labs/<lab_token>/attempts/ — attempt history for this lab."""

    serializer_class = AttemptSerializer
    throttle_scope = "lab_api"

    def get_queryset(self):
        lab = get_owned_lab(self.request, self.kwargs["lab_token"])
        return Attempt.objects.filter(lab=lab).order_by("attempt_number")


class LabLoginView(APIView):
    """
    POST /api/labs/<lab_token>/login/ — the training authentication endpoint.

    This is the target of the student's standalone brute-force script.  The
    student runs a plain Python ``requests`` loop that reads candidate
    passwords from a local text file and POSTs ``{username, password}`` here —
    no platform login inside the script.

    Authorization model: the **unguessable, per-student lab token in the URL is
    the credential** (a capability).  Only the owning student (and staff) are
    ever shown a lab's token, so possession of it authorizes attempts against
    that lab.  This keeps the exercise a clean standalone script.  Every attempt
    is still logged (with IP/user-agent) to that lab, so activity is fully
    attributable, and infrastructure throttling (``lab_login`` scope, keyed by
    client IP) protects the shared server.

    Password guessing itself is intentionally NOT rate-limited inside the lab —
    that is the whole exercise.
    """

    # Intentionally NO rate-limiting: this is the deliberately-vulnerable
    # training target and must be freely attackable at full speed.  The per-lab
    # ``max_attempts`` cap and lab expiry are the only limits.
    throttle_classes = []
    # Token-only: no session/login required, so the standalone script stays
    # simple.  (No SessionAuthentication -> no CSRF enforcement either.)
    authentication_classes = []
    permission_classes = [AllowAny]

    # Map service outcomes to HTTP status codes.
    _STATUS_BY_OUTCOME = {
        Outcome.SUCCESS: status.HTTP_200_OK,
        Outcome.FAILED: status.HTTP_401_UNAUTHORIZED,
        Outcome.LIMIT_REACHED: status.HTTP_429_TOO_MANY_REQUESTS,
        Outcome.EXPIRED: status.HTTP_410_GONE,
        Outcome.DISABLED: status.HTTP_403_FORBIDDEN,
        Outcome.ALREADY_COMPLETED: status.HTTP_409_CONFLICT,
    }

    def post(self, request, lab_token):
        # The token is the capability: look the lab up directly. An unknown
        # token returns 404 (existence of other labs is never revealed).
        lab = get_object_or_404(Lab, lab_token=lab_token)

        in_serializer = TrainingLoginSerializer(data=request.data)
        in_serializer.is_valid(raise_exception=True)
        username = in_serializer.validated_data["username"]
        password = in_serializer.validated_data["password"]

        result = process_login_attempt(
            lab_token=lab.lab_token,
            username=username,
            password=password,
            request=request,
        )

        body = {
            "success": result.success,
            "message": result.message,
        }
        if result.attempt_number is not None:
            body["attempt_number"] = result.attempt_number
        # Always surface live counters for teaching clarity.
        body["attempt_count"] = result.lab.attempt_count
        body["max_attempts"] = result.lab.max_attempts
        body["status"] = result.lab.status

        http_status = self._STATUS_BY_OUTCOME.get(
            result.outcome, status.HTTP_400_BAD_REQUEST
        )
        return Response(body, status=http_status)


# ===========================================================================
# Tokenless public API — the single, "normal" attack surface.
#
# There is one global target account (the primary lab).  Students hit these
# fixed endpoints with no token and no login:
#   GET  /api/target/       -> {"username": ...}   the account to attack
#   GET  /api/wordlist.txt  -> the candidate password list, one per line
#   POST /api/login/        -> {"username","password"} attack the account
# ===========================================================================
class _PublicMixin:
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []  # freely attackable


class PublicTargetView(_PublicMixin, APIView):
    """GET /api/target/ — the username of the account students must break into."""

    def get(self, request):
        lab = get_primary_lab()
        if lab is None:
            return Response({"detail": "No target configured."}, status=503)
        return Response({"username": lab.username})


class PublicWordlistView(_PublicMixin, APIView):
    """GET /api/wordlist.txt — the candidate password list (one per line)."""

    def get(self, request):
        lab = get_primary_lab()
        passwords = []
        if lab is not None:
            passwords = [p for p in (lab.wordlist.passwords or []) if isinstance(p, str)]
        body = "\n".join(passwords) + ("\n" if passwords else "")
        return HttpResponse(body, content_type="text/plain; charset=utf-8")


class PublicLoginView(_PublicMixin, APIView):
    """POST /api/login/ — the tokenless training login (the attack target)."""

    def post(self, request):
        lab = get_primary_lab()
        if lab is None:
            return Response(
                {"success": False, "message": "No target configured."}, status=503
            )
        in_serializer = TrainingLoginSerializer(data=request.data)
        in_serializer.is_valid(raise_exception=True)
        result = process_login_attempt(
            lab_token=lab.lab_token,
            username=in_serializer.validated_data["username"],
            password=in_serializer.validated_data["password"],
            request=request,
            public_mode=True,
        )
        body = {
            "success": result.success,
            "message": result.message,
            "attempt_number": result.attempt_number,
        }
        http_status = status.HTTP_200_OK if result.success else status.HTTP_401_UNAUTHORIZED
        return Response(body, status=http_status)
