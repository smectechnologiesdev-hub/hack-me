"""
Dashboard views.

* ``DashboardHomeView`` — the student landing area after login: a summary of
  their own labs.
* Instructor views — aggregate statistics and recent activity across ALL labs,
  gated behind ``is_staff`` (never accessible to students).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.attempts.models import Attempt
from apps.labs.models import Lab
from apps.labs.services import (
    create_lab_for_student,
    get_or_create_primary_lab,
    set_primary_lab,
)

User = get_user_model()


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    """/dashboard/ — the single post-login landing page: your current challenge.

    Shows one focused challenge (auto-created on first login).  The student runs
    their script against it and, the moment it's cracked, the page celebrates —
    revealing the password and how many attempts it took.
    """

    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Everyone attacks the same global target via the tokenless endpoint.
        lab = get_or_create_primary_lab()
        context["lab"] = lab
        context["wordlist"] = lab.wordlist
        # The fixed, tokenless endpoints the student's script uses.
        context["login_endpoint"] = self.request.build_absolute_uri("/api/login/")
        context["target_endpoint"] = self.request.build_absolute_uri("/api/target/")
        context["wordlist_endpoint"] = self.request.build_absolute_uri("/api/wordlist.txt")
        context["is_instructor"] = self.request.user.is_staff
        return context


class NewChallengeView(LoginRequiredMixin, View):
    """POST /dashboard/new/ — (staff) rotate the global target account."""

    def post(self, request):
        if request.user.is_staff:
            lab = create_lab_for_student(request.user)
            set_primary_lab(lab)
        return redirect("dashboard:home")


class InstructorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to staff/instructor accounts only.

    Students failing the test get a 403 (raise_exception=True) rather than a
    redirect loop.
    """

    raise_exception = True

    def test_func(self):
        return self.request.user.is_staff


class InstructorDashboardView(InstructorRequiredMixin, TemplateView):
    """/instructor/ — platform-wide overview and success metrics."""

    template_name = "instructor/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        total_attempts = Attempt.objects.count()
        successful_attempts = Attempt.objects.filter(success=True).count()
        success_rate = (
            round((successful_attempts / total_attempts) * 100, 1)
            if total_attempts
            else 0.0
        )

        context["overview"] = {
            "total_students": User.objects.filter(
                role=User.Role.STUDENT
            ).count(),
            "active_labs": Lab.objects.filter(status=Lab.Status.ACTIVE).count(),
            "completed_labs": Lab.objects.filter(
                status=Lab.Status.COMPLETED
            ).count(),
            "total_labs": Lab.objects.count(),
            "total_attempts": total_attempts,
            "success_rate": success_rate,
        }

        # Recent activity feed (latest attempts across all labs).
        context["recent_attempts"] = (
            Attempt.objects.select_related("lab", "lab__student")
            .order_by("-created_at")[:25]
        )
        context["now"] = timezone.now()
        return context


class InstructorLabListView(InstructorRequiredMixin, ListView):
    """/instructor/labs/ — filterable list of every lab."""

    template_name = "instructor/lab_list.html"
    context_object_name = "labs"
    paginate_by = 50

    def get_queryset(self):
        qs = (
            Lab.objects.select_related("student", "wordlist")
            .annotate(
                success_count=Count(
                    "attempts", filter=Q(attempts__success=True)
                )
            )
            .order_by("-started_at")
        )
        # Optional filters.
        status = self.request.GET.get("status")
        if status in dict(Lab.Status.choices):
            qs = qs.filter(status=status)
        student = self.request.GET.get("student")
        if student:
            qs = qs.filter(student__username__icontains=student)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = Lab.Status.choices
        context["current_status"] = self.request.GET.get("status", "")
        context["current_student"] = self.request.GET.get("student", "")
        return context


class InstructorAttemptListView(InstructorRequiredMixin, ListView):
    """/instructor/attempts/ — filterable global attempt log."""

    template_name = "instructor/attempt_list.html"
    context_object_name = "attempts"
    paginate_by = 100

    def get_queryset(self):
        qs = Attempt.objects.select_related("lab", "lab__student").order_by(
            "-created_at"
        )
        result = self.request.GET.get("result")
        if result == "success":
            qs = qs.filter(success=True)
        elif result == "failed":
            qs = qs.filter(success=False)
        student = self.request.GET.get("student")
        if student:
            qs = qs.filter(lab__student__username__icontains=student)
        lab_token = self.request.GET.get("lab")
        if lab_token:
            qs = qs.filter(lab__lab_token__icontains=lab_token)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_result"] = self.request.GET.get("result", "")
        context["current_student"] = self.request.GET.get("student", "")
        context["current_lab"] = self.request.GET.get("lab", "")
        return context
