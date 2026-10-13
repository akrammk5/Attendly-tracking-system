import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q
import core.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("timezone", models.CharField(default="Europe/Warsaw", max_length=64, validators=[core.models.validate_timezone])),
                ("color", models.CharField(default="#16a6a1", max_length=7)),
                ("trial_ends_at", models.DateTimeField(default=core.models.trial_expiry)),
                ("license_active", models.BooleanField(default=False)),
                ("seats", models.PositiveIntegerField(default=25)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="Location",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("name", models.CharField(max_length=120)),
                ("active", models.BooleanField(default=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="locations", to="core.company")),
            ],
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("role", models.CharField(choices=[("owner", "Owner"), ("admin", "Administrator"), ("manager", "Manager"), ("employee", "Employee")], default="employee", max_length=12)),
                ("active", models.BooleanField(default=True)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="core.company")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendly_memberships", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Shift",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("corrected", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shifts", to="core.company")),
                ("location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.location")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attendly_shifts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-started_at"]},
        ),
        migrations.CreateModel(
            name="BreakPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("shift", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="breaks", to="core.shift")),
            ],
        ),
        migrations.CreateModel(
            name="LeaveRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("start", models.DateField()),
                ("end", models.DateField()),
                ("reason", models.CharField(blank=True, max_length=200)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leave_requests", to="core.company")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Invitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("email", models.EmailField(max_length=254)),
                ("role", models.CharField(choices=[("owner", "Owner"), ("admin", "Administrator"), ("manager", "Manager"), ("employee", "Employee")], default="employee", max_length=12)),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.company")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("action", models.CharField(max_length=70)),
                ("details", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audit_events", to="core.company")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ("stripe_session_id", models.CharField(max_length=200, unique=True)),
                ("stripe_event_id", models.CharField(blank=True, default="", max_length=200)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.company")),
            ],
        ),
        migrations.AddConstraint(
            model_name="location",
            constraint=models.UniqueConstraint(fields=("company", "name"), name="unique_company_location"),
        ),
        migrations.AddConstraint(
            model_name="membership",
            constraint=models.UniqueConstraint(fields=("company", "user"), name="unique_company_membership"),
        ),
        migrations.AddConstraint(
            model_name="shift",
            constraint=models.UniqueConstraint(condition=Q(ended_at__isnull=True), fields=("company", "user"), name="unique_open_shift"),
        ),
        migrations.AddConstraint(
            model_name="shift",
            constraint=models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F("started_at")), name="valid_shift_interval"),
        ),
        migrations.AddConstraint(
            model_name="breakperiod",
            constraint=models.UniqueConstraint(condition=Q(ended_at__isnull=True), fields=("shift",), name="unique_open_break"),
        ),
        migrations.AddConstraint(
            model_name="breakperiod",
            constraint=models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gt=F("started_at")), name="valid_break_interval"),
        ),
        migrations.AddConstraint(
            model_name="leaverequest",
            constraint=models.CheckConstraint(condition=Q(end__gte=F("start")), name="valid_leave_dates"),
        ),
    ]
