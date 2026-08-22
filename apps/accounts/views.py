"""Registration / login / logout views."""

from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import StudentRegistrationForm, StyledAuthenticationForm


class RegisterView(CreateView):
    """Self-service student registration; logs the user straight in on success."""

    form_class = StudentRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("dashboard:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        # self.object is the freshly created user.
        login(self.request, self.object)
        return response

    def dispatch(self, request, *args, **kwargs):
        # Already-authenticated users don't need to register again.
        if request.user.is_authenticated:
            from django.shortcuts import redirect

            return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)


class LabLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = StyledAuthenticationForm
    redirect_authenticated_user = True


class LabLogoutView(LogoutView):
    """Logout (POST only, per Django's CSRF-safe default)."""
