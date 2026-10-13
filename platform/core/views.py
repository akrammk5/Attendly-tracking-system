import csv
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core import signing
from django.core.mail import send_mail
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import CompanyForm, InviteForm, JoinForm, LeaveForm, LocationForm, SignupForm
from .models import AuditEvent, Company, Invitation, LeaveRequest, Location, Membership, Payment, Shift
from .services import ClockError, audit as audit_record, clock_action, membership_for, require_role

MANAGEMENT = (Membership.OWNER, Membership.ADMIN, Membership.MANAGER)
ADMINISTRATORS = (Membership.OWNER, Membership.ADMIN)


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({"status": "ok"})
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)


def company_scope(request, slug, roles=None):
    company = get_object_or_404(Company, slug=slug)
    member = membership_for(request.user, company)
    if roles:
        require_role(member, roles)
    return company, member


def page(request, template, company, member, **kwargs):
    workspaces = Membership.objects.filter(user=request.user, active=True).select_related("company")
    return render(request, template, {"company": company, "member": member, "workspaces": workspaces, **kwargs})


def landing(request):
    return render(request, "landing.html")


@login_required
def home(request):
    first = Membership.objects.filter(user=request.user, active=True).select_related("company").first()
    if first:
        return redirect("dashboard", slug=first.company.slug)
    return render(request, "auth/no_company.html")


def signup(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        user_model = get_user_model()
        if not settings.DEBUG and not settings.EMAIL_HOST:
            form.add_error(None, "Workspace registration is unavailable until email verification is configured.")
        elif user_model.objects.filter(username__iexact=data["email"]).exists():
            form.add_error("email", "An account with this email already exists.")
        else:
            slug = (slugify(data["company"])[:65] or "company") + "-" + secrets.token_hex(4)
            try:
                with transaction.atomic():
                    user = user_model.objects.create_user(username=data["email"], email=data["email"],
                        password=data["password"], is_active=False)
                    company = Company.objects.create(name=data["company"], slug=slug)
                    Membership.objects.create(company=company, user=user, role=Membership.OWNER)
                    token = signing.dumps({"uid": user.pk}, salt="attendly-email-verification")
                    url = request.build_absolute_uri(reverse("verify_email", args=[token]))
                    send_mail("Verify your Attendly workspace email",
                        "Confirm that you own this email to activate your account:\n" + url +
                        "\n\nThis link expires after 48 hours.",
                        settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
                    audit_record(company, user, "company.created", "Pending email verification")
            except Exception:
                logging.getLogger(__name__).exception("Owner signup verification failed")
                form.add_error(None, "Unable to send a verification email. Check email configuration.")
            else:
                messages.success(request, "Check your email for an activation link before signing in.")
                return redirect("login")
    return render(request, "auth/signup.html", {"form": form})


def verify_email(request, token):
    try:
        value = signing.loads(token, salt="attendly-email-verification", max_age=172800)
        user = get_object_or_404(get_user_model(), pk=value["uid"])
    except (signing.BadSignature, signing.SignatureExpired, KeyError, ValueError, TypeError):
        return render(request, "auth/invite_expired.html", status=410)
    if user.is_active:
        return redirect('login')
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
        membership = Membership.objects.filter(user=user, role=Membership.OWNER).select_related("company").first()
        if membership:
            audit_record(membership.company, user, "email.verified")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("home")


def accept_invite(request, token):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation = get_object_or_404(Invitation.objects.select_related("company"), token_hash=token_hash)
    if invitation.accepted_at or invitation.expires_at < timezone.now():
        return render(request, "auth/invite_expired.html", status=410)
    form = JoinForm(request.POST or None)
    if request.user.is_authenticated and request.user.email.lower() != invitation.email.lower():
        raise PermissionDenied("Log out and use the invited email account.")
    if request.method == "POST" and (request.user.is_authenticated or form.is_valid()):
        with transaction.atomic():
            item = Invitation.objects.select_for_update().select_related("company").get(pk=invitation.pk)
            company = Company.objects.select_for_update().get(pk=item.company_id)
            if item.accepted_at or item.expires_at < timezone.now():
                return render(request, "auth/invite_expired.html", status=410)
            if Membership.objects.filter(company=company, active=True).count() >= company.seats:
                messages.error(request, "This company has no remaining seats.")
                return redirect("login")
            if request.user.is_authenticated:
                user = request.user
            else:
                user = get_user_model().objects.filter(username__iexact=item.email).first()
                if user:
                    # Secure one-time bootstrap: permit a pre-provisioned inactive account
                    # with an unusable password to set its first credential via invitation.
                    # Never reset an established user's password through an invitation.
                    if user.is_active or user.has_usable_password() or user.email.lower() != item.email.lower():
                        messages.error(request, "Sign into your existing account to accept your invitation.")
                        return redirect("login")
                    user.set_password(form.cleaned_data["password"])
                    user.is_active = True
                    user.save(update_fields=["password", "is_active"])
                else:
                    user = get_user_model().objects.create_user(username=item.email.lower(), email=item.email.lower(), password=form.cleaned_data["password"])
            membership, created = Membership.objects.get_or_create(company=company, user=user, defaults={"role": item.role})
            if not created:
                membership.active = True
                membership.save(update_fields=["active"])
            item.accepted_at = timezone.now()
            item.save(update_fields=["accepted_at"])
            audit_record(company, user, "invite.accepted")
        if not request.user.is_authenticated:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("dashboard", slug=company.slug)
    return render(request, "auth/accept_invite.html", {"invitation": invitation, "form": form})


@login_required
def dashboard(request, slug):
    company, member = company_scope(request, slug)
    if member.role == Membership.EMPLOYEE:
        return redirect("clock", slug=slug)
    active = company.shifts.filter(ended_at__isnull=True).count()
    staff = Membership.objects.filter(company=company, active=True).count()
    pending = LeaveRequest.objects.filter(company=company, status="pending").count()
    recent = Shift.objects.filter(company=company).select_related("user", "location")[:12]
    return page(request, "dashboard.html", company, member, active=active, staff=staff,
                pending=pending, recent=recent, license_ok=company.is_entitled)


@login_required
def clock(request, slug):
    company, member = company_scope(request, slug)
    if request.method == "POST":
        action = request.POST.get("action", "")
        location_id = request.POST.get("location", "") or None
        try:
            msg, shift = clock_action(company, request.user, action, location_id)
            messages.success(request, msg)
        except ClockError as exc:
            messages.error(request, str(exc))
        return redirect("clock", slug=slug)
    current = Shift.objects.filter(company=company, user=request.user, ended_at__isnull=True).prefetch_related("breaks").first()
    on_break = bool(current and current.breaks.filter(ended_at__isnull=True).exists())
    history = Shift.objects.filter(company=company, user=request.user).prefetch_related("breaks")[:15]
    locations_list = Location.objects.filter(company=company, active=True)
    local_now = timezone.localtime(timezone.now(), ZoneInfo(company.timezone))
    return page(request, "clock.html", company, member, current=current, on_break=on_break,
                history=history, locations=locations_list, local_now=local_now)


@login_required
def team(request, slug):
    company, member = company_scope(request, slug, MANAGEMENT)
    people = Membership.objects.filter(company=company).select_related("user").order_by("user__username")
    invites = Invitation.objects.filter(company=company, accepted_at__isnull=True, expires_at__gt=timezone.now()).order_by("-created_at")[:10]
    return page(request, "team.html", company, member, people=people, invites=invites)


@login_required
def invite(request, slug):
    company, member = company_scope(request, slug, ADMINISTRATORS)
    form = InviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not settings.EMAIL_HOST:
            messages.error(request, "Configure SMTP before inviting employees.")
        elif Membership.objects.filter(company=company, active=True).count() >= company.seats:
            messages.error(request, "Your company is at the seat limit.")
        elif Membership.objects.filter(company=company, user__email__iexact=form.cleaned_data["email"], active=True).exists():
            messages.error(request, "This person is already a member.")
        else:
            raw = secrets.token_urlsafe(32)
            item = Invitation.objects.create(company=company, email=form.cleaned_data["email"],
                role=form.cleaned_data["role"], token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                expires_at=timezone.now() + timedelta(days=3), created_by=request.user)
            invitation_url = request.build_absolute_uri(reverse("accept_invite", args=[raw]))
            try:
                send_mail("You're invited to " + company.name + " on Attendly",
                    "An administrator invited you to Attendly. This invitation expires in 3 days:\n" + invitation_url,
                    settings.DEFAULT_FROM_EMAIL, [item.email], fail_silently=False)
            except Exception:
                item.delete()
                messages.error(request, "Email delivery failed. Verify SMTP settings and try again.")
            else:
                audit_record(company, request.user, "invite.created", "Invitation sent")
                messages.success(request, "Invitation sent securely.")
                return redirect("team", slug=slug)
    return page(request, "form.html", company, member, form=form, title="Invite team member",
                subtitle="Send a private sign-up link. Invitations expire after three days.")


@require_POST
@login_required
def update_team(request, slug, membership_id):
    company, member = company_scope(request, slug, ADMINISTRATORS)
    target = get_object_or_404(Membership, company=company, pk=membership_id)
    desired_role = request.POST.get("role")
    if target.role == Membership.OWNER:
        messages.error(request, "Owner accounts cannot be changed here.")
    elif desired_role in dict(Membership.ROLE_CHOICES):
        if desired_role == Membership.OWNER:
            messages.error(request, "Ownership transfer requires a separate verified process.")
        else:
            target.role = desired_role
            target.save(update_fields=["role"])
            audit_record(company, request.user, "team.role_changed", "membership:" + str(target.pk))
            messages.success(request, "Team role updated.")
    elif request.POST.get("action") == "deactivate":
        target.active = False
        target.save(update_fields=["active"])
        audit_record(company, request.user, "team.deactivated", "membership:" + str(target.pk))
        messages.success(request, "Team access disabled.")
    else:
        messages.error(request, "Invalid team update.")
    return redirect("team", slug=slug)


@login_required
def locations(request, slug):
    company, member = company_scope(request, slug, ADMINISTRATORS)
    form = LocationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            Location.objects.create(company=company, **form.cleaned_data)
        except IntegrityError:
            form.add_error("name", "This location already exists.")
        else:
            audit_record(company, request.user, "location.created")
            messages.success(request, "Location added.")
            return redirect("locations", slug=slug)
    return page(request, "locations.html", company, member, form=form, locations=Location.objects.filter(company=company))


@login_required
def shifts(request, slug):
    company, member = company_scope(request, slug, MANAGEMENT)
    entries = Shift.objects.filter(company=company).select_related("user", "location").prefetch_related("breaks")
    return page(request, "shifts.html", company, member, shifts=entries[:100])


@login_required
def correct_shift(request, slug, shift_id):
    company, member = company_scope(request, slug, MANAGEMENT)
    item = get_object_or_404(Shift, company=company, pk=shift_id)
    if request.method == "POST":
        try:
            start_naive = datetime.fromisoformat(request.POST.get("started_at", ""))
            end_naive = datetime.fromisoformat(request.POST.get("ended_at", ""))
            if start_naive.tzinfo or end_naive.tzinfo:
                raise ValueError
            zone = ZoneInfo(company.timezone)
            start = timezone.make_aware(start_naive, zone)
            end = timezone.make_aware(end_naive, zone)
            if not request.POST.get("note", "").strip() or end <= start or end - start > timedelta(hours=36):
                raise ValueError
            conflicting = Shift.objects.filter(company=company, user=item.user, started_at__lt=end).filter(
                Q(ended_at__gt=start) | Q(ended_at__isnull=True)
            ).exclude(pk=item.pk).exists()
            if conflicting:
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            messages.error(request, "Enter valid local times (up to 36 hours), without overlapping another shift.")
        else:
            with transaction.atomic():
                Company.objects.select_for_update().get(pk=company.pk)
                item = Shift.objects.select_for_update().get(pk=item.pk, company=company)
                if item.breaks.filter(Q(started_at__lt=start) | Q(started_at__gte=end) | Q(ended_at__gt=end)).exists():
                    messages.error(request, "Recorded breaks fall outside the proposed shift. Have an administrator review the break history first.")
                    return redirect("correct_shift", slug=slug, shift_id=item.pk)
                previous = item.started_at.isoformat() + " / " + str(item.ended_at)
                item.started_at, item.ended_at, item.corrected = start, end, True
                item.note = request.POST.get("note", "")[:250]
                item.save(update_fields=["started_at", "ended_at", "corrected", "note"])
                audit_record(company, request.user, "shift.corrected", "shift:" + str(item.pk) + " previous:" + previous[:160])
            messages.success(request, "Shift corrected; previous times recorded in audit history.")
            return redirect("shifts", slug=slug)
    return page(request, "correct_shift.html", company, member, shift=item)


@login_required
def leave(request, slug):
    company, member = company_scope(request, slug)
    form = LeaveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        req = form.save(commit=False)
        req.company, req.user = company, request.user
        req.save()
        audit_record(company, request.user, "leave.requested", "request:" + str(req.pk))
        messages.success(request, "Leave request submitted.")
        return redirect("leave", slug=slug)
    own = LeaveRequest.objects.filter(company=company, user=request.user).order_by("-created_at")[:30]
    pending = LeaveRequest.objects.filter(company=company, status="pending").select_related("user")[:50] if member.role in MANAGEMENT else []
    return page(request, "leave.html", company, member, form=form, own=own, pending=pending)


@require_POST
@login_required
def review_leave(request, slug, request_id):
    company, member = company_scope(request, slug, MANAGEMENT)
    desired = request.POST.get("decision")
    if desired not in ("approved", "rejected"):
        messages.error(request, "Invalid decision.")
        return redirect("leave", slug=slug)
    with transaction.atomic():
        obj = get_object_or_404(LeaveRequest.objects.select_for_update(), company=company, pk=request_id, status="pending")
        if obj.user_id == request.user.id:
            raise PermissionDenied("You cannot approve your own leave.")
        obj.status, obj.reviewed_by = desired, request.user
        obj.save(update_fields=["status", "reviewed_by"])
        audit_record(company, request.user, "leave." + desired, "request:" + str(obj.pk))
    messages.success(request, "Request reviewed.")
    return redirect("leave", slug=slug)


def filtered_shifts(request, company):
    start_text = request.GET.get("start", "")
    end_text = request.GET.get("end", "")
    today = timezone.localtime(timezone.now(), ZoneInfo(company.timezone)).date()
    try:
        start = datetime.strptime(start_text, "%Y-%m-%d").date() if start_text else today - timedelta(days=30)
        end = datetime.strptime(end_text, "%Y-%m-%d").date() if end_text else today
        if end < start or (end - start).days > 366:
            raise ValueError
    except ValueError:
        return [], None, None
    zone = ZoneInfo(company.timezone)
    start_dt = timezone.make_aware(datetime.combine(start, datetime.min.time()), zone)
    end_dt = timezone.make_aware(datetime.combine(end + timedelta(days=1), datetime.min.time()), zone)
    records = Shift.objects.filter(company=company, started_at__gte=start_dt, started_at__lt=end_dt).select_related("user", "location").prefetch_related("breaks").order_by("-started_at")
    return records, start, end


@login_required
def reports(request, slug):
    company, member = company_scope(request, slug, MANAGEMENT)
    entries, start, end = filtered_shifts(request, company)
    if start is None:
        messages.error(request, "Choose a valid date range, no longer than one year.")
        entries = []
    return page(request, "reports.html", company, member, shifts=list(entries[:500]), start=start, end=end)


def csv_safe(value):
    val = str(value or "")
    return "'" + val if val.startswith(("=", "+", "-", "@", "\t", "\r")) else val


@login_required
def export_csv(request, slug):
    company, member = company_scope(request, slug, MANAGEMENT)
    entries, start, end = filtered_shifts(request, company)
    if start is None:
        return HttpResponse("Invalid date range.", status=400)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="attendly-report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Employee", "Email", "Location", "Start UTC", "End UTC", "Net Hours", "Corrected"])
    for shift in entries.iterator(chunk_size=200):
        writer.writerow([csv_safe(shift.user.get_full_name() or shift.user.email),
            csv_safe(shift.user.email), csv_safe(shift.location.name if shift.location else ""),
            shift.started_at.isoformat(), shift.ended_at.isoformat() if shift.ended_at else "",
            shift.hours if shift.hours is not None else "", shift.corrected])
    audit_record(company, request.user, "report.exported", str(start) + " to " + str(end))
    return response


@login_required
def audit(request, slug):
    company, member = company_scope(request, slug, ADMINISTRATORS)
    entries = AuditEvent.objects.filter(company=company).select_related("actor")[:150]
    return page(request, "audit.html", company, member, events=entries)


@login_required
def settings_page(request, slug):
    company, member = company_scope(request, slug, (Membership.OWNER,))
    form = CompanyForm(request.POST or None, instance=company)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit_record(company, request.user, "company.settings")
        messages.success(request, "Company settings updated.")
        return redirect("settings", slug=slug)
    return page(request, "form.html", company, member, form=form, title="Company settings",
                subtitle="Configure branding and the official company time zone.")


@login_required
def billing(request, slug):
    company, member = company_scope(request, slug, (Membership.OWNER,))
    enabled = bool(settings.STRIPE_PRICE_ID and settings.STRIPE_WEBHOOK_SECRET and settings.STRIPE_SECRET_KEY)
    return page(request, "billing.html", company, member, enabled=enabled)


@require_POST
@login_required
def checkout(request, slug):
    company, member = company_scope(request, slug, (Membership.OWNER,))
    if company.license_active:
        messages.info(request, "Your company's license is already active.")
        return redirect("billing", slug=slug)
    if not all([settings.STRIPE_SECRET_KEY, settings.STRIPE_PRICE_ID, settings.STRIPE_WEBHOOK_SECRET]):
        messages.error(request, "The payment gateway has not been configured.")
        return redirect("billing", slug=slug)
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.create(mode="payment",
            line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
            client_reference_id=str(company.pk),
            metadata={"company_id": str(company.pk)},
            success_url=request.build_absolute_uri(reverse("billing", args=[slug])) + "?checkout=success",
            cancel_url=request.build_absolute_uri(reverse("billing", args=[slug])) + "?checkout=canceled")
        Payment.objects.create(company=company, stripe_session_id=session.id)
    except Exception:
        messages.error(request, "Unable to start checkout. Please contact support.")
        return redirect("billing", slug=slug)
    return redirect(session.url)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=503)
    import stripe
    try:
        event = stripe.Webhook.construct_event(
            request.body, request.headers.get("Stripe-Signature", ""), settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)
    kind = event["type"]
    payload = event["data"]["object"]
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if payload.get("payment_status") == "paid" and payload.get("mode") == "payment":
            with transaction.atomic():
                payment = Payment.objects.select_for_update().filter(stripe_session_id=payload.get("id")).first()
                if payment and str(payment.company_id) == str(payload.get("client_reference_id")) and not payment.paid_at:
                    Company.objects.select_for_update().get(pk=payment.company_id)
                    payment.paid_at = timezone.now()
                    payment.stripe_event_id = str(event["id"])[:200]
                    payment.stripe_payment_intent_id = payload.get("payment_intent") or None
                    payment.save(update_fields=["paid_at", "stripe_event_id", "stripe_payment_intent_id"])
                    Company.objects.filter(pk=payment.company_id).update(license_active=True)
                    audit_record(payment.company, None, "license.activated", "verified Stripe checkout")
    elif kind == "charge.refunded" and payload.get("refunded") is True:
        # Partial refunds do not revoke licenses. Only full charge refunds do.
        intent_id = payload.get("payment_intent")
        if intent_id:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().filter(
                    stripe_payment_intent_id=intent_id, paid_at__isnull=False, refunded_at__isnull=True
                ).first()
                if payment:
                    Company.objects.select_for_update().get(pk=payment.company_id)
                    payment.refunded_at = timezone.now()
                    payment.stripe_event_id = str(event["id"])[:200]
                    payment.save(update_fields=["refunded_at", "stripe_event_id"])
                    has_other_payment = Payment.objects.filter(
                        company_id=payment.company_id, paid_at__isnull=False, refunded_at__isnull=True
                    ).exists()
                    if not has_other_payment:
                        Company.objects.filter(pk=payment.company_id).update(license_active=False)
                    audit_record(payment.company, None, "license.refunded", "verified full payment refund")
    return HttpResponse(status=200)
