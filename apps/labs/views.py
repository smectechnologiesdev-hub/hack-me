"""
HTML (template) views for the student-facing lab pages.

All views require login.  Per-lab pages enforce object-level ownership through
``get_owned_lab`` so a student can never open another student's lab by editing
the token in the URL.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, TemplateView

from .models import Lab
from .permissions import get_owned_lab
from .services import create_lab_for_student, refresh_lab_status


def _wordlist_txt_response(lab: Lab) -> HttpResponse:
    """Build a ``passwords.txt`` file download (one password per line)."""
    passwords = [p for p in (lab.wordlist.passwords or []) if isinstance(p, str)]
    body = "\n".join(passwords) + "\n"
    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    filename = f"passwords_{lab.lab_token[:8]}.txt"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class LabListView(LoginRequiredMixin, ListView):
    """/labs/ — the student's own labs (and a button to start a new one)."""

    template_name = "labs/lab_list.html"
    context_object_name = "labs"

    def get_queryset(self):
        return (
            Lab.objects.filter(student=self.request.user)
            .select_related("wordlist")
            .order_by("-started_at")
        )


class LabStartView(LoginRequiredMixin, View):
    """POST target for the "Start new lab" button (creates + redirects)."""

    def post(self, request):
        difficulty = request.POST.get("difficulty") or None
        lab = create_lab_for_student(request.user, difficulty=difficulty)
        return redirect(reverse("labs:detail", kwargs={"lab_token": lab.lab_token}))


class _OwnedLabMixin(LoginRequiredMixin):
    """Mixin that loads the owned lab and refreshes its status."""

    def get_lab(self):
        lab = get_owned_lab(self.request, self.kwargs["lab_token"])
        return refresh_lab_status(lab)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lab = self.get_lab()
        context["lab"] = lab
        context["login_path"] = reverse(
            "labs_api:lab-login", kwargs={"lab_token": lab.lab_token}
        )
        return context


class LabDetailView(_OwnedLabMixin, TemplateView):
    """/labs/<token>/ — overview + credentials + quick links."""

    template_name = "labs/lab_detail.html"


class LabInstructionsView(_OwnedLabMixin, TemplateView):
    """/labs/<token>/instructions/ — the interactive learning + exercise page."""

    template_name = "labs/lab_instructions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["wordlist"] = context["lab"].wordlist
        return context


class LabMonitorView(_OwnedLabMixin, TemplateView):
    """/labs/<token>/monitor/ — the live WebSocket dashboard."""

    template_name = "labs/lab_monitor.html"


class LabWordlistDownloadView(LoginRequiredMixin, View):
    """/labs/<token>/wordlist.txt — owner download of the assigned wordlist.

    The logged-in owner (or staff) downloads their wordlist as ``passwords.txt``
    (one password per line) to feed their script.
    """

    def get(self, request, lab_token):
        lab = get_owned_lab(request, lab_token)
        return _wordlist_txt_response(lab)
