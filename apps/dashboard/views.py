"""
Dashboard views.

* ``DashboardHomeView`` — the single post-login landing page: the account
  "vault".  When you've just signed in (including with cracked credentials), it
  celebrates: ACCESS GRANTED.
* Instructor views — aggregate views over the legacy lab data, gated behind
  ``is_staff``.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.utils import timezone
from django.views.generic import ListView, TemplateView

from apps.attempts.models import Attempt
from apps.labs.models import Lab

User = get_user_model()


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    """/dashboard/ — the participant's mission briefing.

    Shows the student their assigned target, the starter script, tiered hints,
    live progress, and the flag-submission form.
    """

    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        from apps.challenge.models import VaultClient

        context = super().get_context_data(**kwargs)
        context["just_accessed"] = self.request.session.pop("just_accessed", False)
        context["is_instructor"] = self.request.user.is_staff
        context["target"] = VaultClient.objects.filter(
            assigned_to=self.request.user
        ).first()
        context["flag_result"] = self.request.session.pop("flag_result", None)
        return context


class InstructorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict a view to staff/instructor accounts only."""

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
            "total_students": User.objects.filter(role=User.Role.STUDENT).count(),
            "active_labs": Lab.objects.filter(status=Lab.Status.ACTIVE).count(),
            "completed_labs": Lab.objects.filter(status=Lab.Status.COMPLETED).count(),
            "total_labs": Lab.objects.count(),
            "total_attempts": total_attempts,
            "success_rate": success_rate,
        }
        context["recent_attempts"] = (
            Attempt.objects.select_related("lab", "lab__student").order_by("-created_at")[:25]
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
            .annotate(success_count=Count("attempts", filter=Q(attempts__success=True)))
            .order_by("-started_at")
        )
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
        qs = Attempt.objects.select_related("lab", "lab__student").order_by("-created_at")
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
