"""Reusable object-level authorisation helpers for labs."""

from django.shortcuts import get_object_or_404

from .models import Lab


def get_owned_lab(request, lab_token: str) -> Lab:
    """Fetch a lab the requesting user is allowed to act on, else 404.

    A student may only reach their OWN lab.  Staff/instructors may reach any
    lab (for support/observation).  We return 404 rather than 403 for
    non-owners so the existence of other students' labs is not revealed.
    """
    lab = get_object_or_404(
        Lab.objects.select_related("wordlist", "student"), lab_token=lab_token
    )
    user = request.user
    if user.is_staff or lab.student_id == user.id:
        return lab
    # Not the owner and not staff -> pretend it doesn't exist.
    from django.http import Http404

    raise Http404("No lab matches the given query.")
