import uuid
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


def trial_expiry():
    return timezone.now() + timedelta(days=14)


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValidationError("Select a valid IANA timezone.")


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True, max_length=80)
    timezone = models.CharField(max_length=64, default="Europe/Warsaw", validators=[validate_timezone])
    color = models.CharField(max_length=7, default="#16a6a1")
    trial_ends_at = models.DateTimeField(default=trial_expiry)
    license_active = models.BooleanField(default=False)
    seats = models.PositiveIntegerField(default=25)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_entitled(self):
        return self.license_active or timezone.now() <= self.trial_ends_at

    def __str__(self):
        return self.name


class Membership(models.Model):
    OWNER, ADMIN, MANAGER, EMPLOYEE = "owner", "admin", "manager", "employee"
    ROLE_CHOICES = [(OWNER, "Owner"), (ADMIN, "Administrator"), (MANAGER, "Manager"), (EMPLOYEE, "Employee")]
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendly_memberships")
    role = models.CharField(max_length=12, choices=ROLE_CHOICES, default=EMPLOYEE)
    active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "user"], name="unique_company_membership")]


class Location(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="locations")
    name = models.CharField(max_length=120)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "name"], name="unique_company_location")]

    def __str__(self):
        return self.name


class Shift(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="shifts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendly_shifts")
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=250, blank=True)
    corrected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(fields=["company", "user"], condition=Q(ended_at__isnull=True), name="unique_open_shift"),
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F("started_at")), name="valid_shift_interval"),
        ]

    @property
    def hours(self):
        if not self.ended_at:
            return None
        seconds = (self.ended_at - self.started_at).total_seconds()
        breaks = sum((min(b.ended_at or self.ended_at, self.ended_at) - b.started_at).total_seconds()
                     for b in self.breaks.all() if b.started_at < self.ended_at)
        return round(max(0, seconds - breaks) / 3600, 2)


class BreakPeriod(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="breaks")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["shift"], condition=Q(ended_at__isnull=True), name="unique_open_break"),
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F("started_at")), name="valid_break_interval"),
        ]


class LeaveRequest(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="leave_requests")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    start = models.DateField()
    end = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(end__gte=F("start")), name="valid_leave_dates")]


class Invitation(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    email = models.EmailField()
    role = models.CharField(max_length=12, choices=Membership.ROLE_CHOICES, default=Membership.EMPLOYEE)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=70)
    details = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Payment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    stripe_session_id = models.CharField(max_length=200, unique=True)
    stripe_event_id = models.CharField(max_length=200, blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
