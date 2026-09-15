"""Authentication forms."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.validators import RegexValidator

User = get_user_model()


class StudentRegistrationForm(UserCreationForm):
    """Self-service registration always creates a Student account.

    The role is fixed server-side; there is no way for a registrant to grant
    themselves instructor privileges through this form.
    """

    phone = forms.CharField(
        required=True,
        max_length=20,
        label="Phone number",
        help_text="Used to reach you.",
        validators=[
            RegexValidator(
                r"^[0-9+\-\s()]{7,20}$",
                "Enter a valid phone number.",
            )
        ],
    )

    class Meta:
        model = User
        fields = ("username", "phone")

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
