from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Company, Membership, Shift, BreakPeriod, LeaveRequest, AuditEvent, Location
from .services import ClockError, clock_action


@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AttendlyPlatformTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner_a = User.objects.create_user(username="owner-a@example.com", email="owner-a@example.com", password="very-strong-owner-passphrase-a")
        cls.owner_b = User.objects.create_user(username="owner-b@example.com", email="owner-b@example.com", password="very-strong-owner-passphrase-b")
        cls.staff_a = User.objects.create_user(username="staff-a@example.com", email="staff-a@example.com", password="very-strong-staff-passphrase-a")
        cls.company_a = Company.objects.create(name="Company Alpha", slug="company-alpha")
        cls.company_b = Company.objects.create(name="Company Beta", slug="company-beta")
        Membership.objects.create(company=cls.company_a, user=cls.owner_a, role=Membership.OWNER)
        Membership.objects.create(company=cls.company_b, user=cls.owner_b, role=Membership.OWNER)
        Membership.objects.create(company=cls.company_a, user=cls.staff_a, role=Membership.EMPLOYEE)

    def url(self, name, company=None, **extra):
        return reverse(name, kwargs={"slug": (company or self.company_a).slug, **extra})

    def test_company_signup_creates_owner_and_private_workspace(self):
        response = self.client.post(reverse("signup"), {
            "company": "New Ventures", "email": "founder@example.com",
            "password": "long-super-secure-founder-password-2026"
        })
        self.assertEqual(response.status_code, 302, str(response.context["form"].errors) if response.context else "")
        m = Membership.objects.get(user__email="founder@example.com")
        self.assertEqual(m.role, Membership.OWNER)
        self.assertEqual(m.company.name, "New Ventures")

    def test_employee_cannot_access_management_routes(self):
        self.client.force_login(self.staff_a)
        for name in ["dashboard", "team", "shifts", "reports", "export_csv", "locations", "billing", "audit", "settings"]:
            with self.subTest(name=name):
                res = self.client.get(self.url(name))
                if name == "dashboard":
                    self.assertEqual(res.status_code, 302)
                else:
                    self.assertEqual(res.status_code, 403)

    def test_staff_cannot_read_another_company_even_if_logged_in(self):
        self.client.force_login(self.staff_a)
        for name in ["clock", "team", "leave", "shifts", "billing"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(self.url(name, self.company_b)).status_code, 403)

    def test_clock_in_break_end_and_clock_out(self):
        self.client.force_login(self.staff_a)
        clock_url = self.url("clock")
        self.assertEqual(self.client.post(clock_url, {"action": "in"}).status_code, 302)
        shift = Shift.objects.get(company=self.company_a, user=self.staff_a)
        self.assertIsNone(shift.ended_at)
        self.assertEqual(self.client.post(clock_url, {"action": "break_start"}).status_code, 302)
        self.assertEqual(self.client.post(clock_url, {"action": "break_end"}).status_code, 302)
        self.assertEqual(BreakPeriod.objects.filter(shift=shift).count(), 1)
        self.assertEqual(self.client.post(clock_url, {"action": "out"}).status_code, 302)
        shift.refresh_from_db()
        self.assertIsNotNone(shift.ended_at)
        self.assertIsInstance(shift.hours, float)
        self.assertEqual(AuditEvent.objects.filter(company=self.company_a).count(), 4)

    def test_duplicate_clock_in_rejected(self):
        clock_action(self.company_a, self.staff_a, "in")
        with self.assertRaises(ClockError):
            clock_action(self.company_a, self.staff_a, "in")
        self.assertEqual(Shift.objects.filter(company=self.company_a, user=self.staff_a).count(), 1)

    def test_clock_out_without_clock_in_rejected(self):
        with self.assertRaises(ClockError):
            clock_action(self.company_a, self.staff_a, "out")

    def test_trial_expiry_blocks_new_clock_ins(self):
        self.company_a.trial_ends_at = timezone.now() - timedelta(days=1)
        self.company_a.save()
        with self.assertRaises(ClockError):
            clock_action(self.company_a, self.staff_a, "in")
        self.assertFalse(Shift.objects.exists())

    def test_location_must_belong_to_same_company(self):
        loc = Location.objects.create(company=self.company_b, name="Other HQ")
        with self.assertRaises(ClockError):
            clock_action(self.company_a, self.staff_a, "in", str(loc.pk))
        self.assertEqual(Shift.objects.count(), 0)

    def test_reports_are_tenant_scoped(self):
        now = timezone.now()
        Shift.objects.create(company=self.company_a, user=self.staff_a, started_at=now-timedelta(hours=3), ended_at=now)
        Shift.objects.create(company=self.company_b, user=self.owner_b, started_at=now-timedelta(hours=3), ended_at=now)
        self.client.force_login(self.owner_a)
        response = self.client.get(self.url("export_csv"))
        self.assertEqual(response.status_code, 200)
        text = response.content.decode()
        self.assertIn("staff-a@example.com", text)
        self.assertNotIn("owner-b@example.com", text)

    def test_exports_prevent_formula_injection(self):
        from .views import csv_safe
        for payload in ("=HYPERLINK('x')", "+SUM(A1)", "-1+2", "@cmd"):
            self.assertTrue(csv_safe(payload).startswith("'"))
        self.assertEqual(csv_safe("Normal"), "Normal")

    def test_unauthorized_owner_transfer_is_blocked(self):
        self.client.force_login(self.owner_a)
        member = Membership.objects.get(company=self.company_a, user=self.staff_a)
        response = self.client.post(self.url("update_team", membership_id=member.pk), {"role": "owner"})
        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        self.assertEqual(member.role, Membership.EMPLOYEE)

    def test_team_membership_cannot_be_updated_from_other_tenant(self):
        self.client.force_login(self.owner_b)
        member = Membership.objects.get(company=self.company_a, user=self.staff_a)
        response = self.client.post(self.url("update_team", self.company_b, membership_id=member.pk), {"role": "admin"})
        self.assertEqual(response.status_code, 404)
        member.refresh_from_db()
        self.assertEqual(member.role, Membership.EMPLOYEE)

    def test_leave_review_cannot_self_approve_or_cross_tenant(self):
        request = LeaveRequest.objects.create(company=self.company_a, user=self.owner_a,
            start=timezone.localdate(), end=timezone.localdate())
        self.client.force_login(self.owner_a)
        response = self.client.post(self.url("review_leave", request_id=request.pk), {"decision": "approved"})
        self.assertEqual(response.status_code, 403)
        request.refresh_from_db()
        self.assertEqual(request.status, "pending")
        self.client.force_login(self.owner_b)
        self.assertEqual(self.client.post(self.url("review_leave", self.company_b, request_id=request.pk), {"decision": "approved"}).status_code, 404)

    def test_unsigned_webhook_rejected(self):
        with override_settings(STRIPE_WEBHOOK_SECRET="whsec_unit_test"):
            self.assertEqual(self.client.post(reverse("stripe_webhook"), data=b"{}", content_type="application/json").status_code, 400)

    def test_invitation_requires_email_configuration(self):
        self.client.force_login(self.owner_a)
        with override_settings(EMAIL_HOST=""):
            response = self.client.post(self.url("invite"), {"email": "joiner@example.com", "role": "employee"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.company_a.invitation_set.count(), 0)

    def test_healthcheck(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.json()["status"], "ok")

    def test_new_owner_must_verify_email_before_signin(self):
        from django.core import mail
        from urllib.parse import urlparse
        response = self.client.post(reverse("signup"), {
            "company": "Secure Email Ventures", "email": "verify-me@example.com",
            "password": "long-unique-verification-password-2026"
        })
        self.assertEqual(response.status_code, 302, str(response.context["form"].errors) if response.context else "")
        user = get_user_model().objects.get(email="verify-me@example.com")
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        verify_url = mail.outbox[0].body.splitlines()[1]
        path = urlparse(verify_url).path
        verify_response = self.client.get(path)
        self.assertEqual(verify_response.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_clock_out_allowed_if_trial_expires_mid_shift(self):
        clock_action(self.company_a, self.staff_a, "in")
        self.company_a.trial_ends_at = timezone.now() - timedelta(days=1)
        self.company_a.save()
        message, shift = clock_action(self.company_a, self.staff_a, "out")
        self.assertIn("clocked out", message.lower())
        self.assertIsNotNone(shift.ended_at)

    def test_manager_correction_preserves_break_history(self):
        from zoneinfo import ZoneInfo
        start = timezone.now() - timedelta(hours=7)
        end = timezone.now() - timedelta(hours=1)
        shift = Shift.objects.create(company=self.company_a, user=self.staff_a, started_at=start, ended_at=end)
        BreakPeriod.objects.create(shift=shift, started_at=start + timedelta(hours=2), ended_at=start + timedelta(hours=2,minutes=30))
        self.client.force_login(self.owner_a)
        loc_start = timezone.localtime(start - timedelta(minutes=10), ZoneInfo(self.company_a.timezone)).strftime("%Y-%m-%dT%H:%M")
        loc_end = timezone.localtime(end + timedelta(minutes=10), ZoneInfo(self.company_a.timezone)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(self.url("correct_shift", shift_id=shift.pk), {
            "started_at": loc_start, "ended_at": loc_end, "note": "Manager verified work time"
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BreakPeriod.objects.filter(shift=shift).count(), 1)
        shift.refresh_from_db()
        self.assertTrue(shift.corrected)

    def test_deactivated_team_member_cannot_clock(self):
        m = Membership.objects.get(company=self.company_a, user=self.staff_a)
        m.active = False
        m.save()
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            clock_action(self.company_a, self.staff_a, "in")
