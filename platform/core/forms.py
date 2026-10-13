from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from .models import Company, Membership, Location, LeaveRequest


class SignupForm(forms.Form):
    company = forms.CharField(max_length=160, label="Company name")
    email = forms.EmailField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput, label="Password", min_length=12)

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password


class JoinForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, min_length=12)

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password


class InviteForm(forms.Form):
    email = forms.EmailField(max_length=150)
    role = forms.ChoiceField(choices=[(Membership.EMPLOYEE, "Employee"), (Membership.MANAGER, "Manager"), (Membership.ADMIN, "Administrator")])

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "timezone", "color"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def clean_color(self):
        import re
        value = self.cleaned_data["color"]
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValidationError("Choose a valid six-digit color.")
        return value


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["name"]


class LeaveForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["start", "end", "reason"]
        widgets = {"start": forms.DateInput(attrs={"type": "date"}), "end": forms.DateInput(attrs={"type": "date"})}

    def clean(self):
        data = super().clean()
        if data.get("end") and data.get("start") and data["end"] < data["start"]:
            raise ValidationError("The end date must not precede the start date.")
        return data
