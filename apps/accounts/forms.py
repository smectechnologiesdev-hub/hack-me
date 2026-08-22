"""Authentication forms."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class StudentRegistrationForm(UserCreationForm):
    """Self-service registration always creates a Student account.

    The role is fixed server-side; there is no way for a registrant to grant
    themselves instructor privileges through this form.
    """

    email = forms.EmailField(required=True, help_text="Used to identify you.")

    class Meta:
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        # Hard-set the role regardless of any submitted data.
        user.role = User.Role.STUDENT
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class StyledAuthenticationForm(AuthenticationForm):
    """Login form (kept as a subclass so we can theme widgets consistently)."""
