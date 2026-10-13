from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, IntegrityError
from django.utils import timezone
from .models import Company, Membership, Shift, BreakPeriod, AuditEvent


class ClockError(Exception):
    pass


def membership_for(user, company):
    if not user.is_authenticated:
        raise PermissionDenied
    member = Membership.objects.filter(company=company, user=user, active=True).first()
    if not member:
        raise PermissionDenied("You are not a member of this company.")
    return member


def require_role(member, allowed):
    if member.role not in allowed:
        raise PermissionDenied("Your role cannot perform this action.")


def audit(company, actor, action, details=""):
    AuditEvent.objects.create(company=company, actor=actor, action=action, details=details[:250])


@transaction.atomic
def clock_action(company, user, action, location_id=None):
    # Lock the tenant row to serialize all shift changes for this company, not
    # just current open shift rows (there may be no row yet).
    locked_company = Company.objects.select_for_update().get(pk=company.pk)
    member = membership_for(user, locked_company)
    if not locked_company.is_entitled and action == "in":
        raise ClockError("The company license is inactive. Ask your administrator.")
    if action not in ("in", "out", "break_start", "break_end"):
        raise ClockError("Unknown time clock action.")
    now = timezone.now()
    shift = Shift.objects.select_for_update().filter(
        company=locked_company, user=user, ended_at__isnull=True
    ).first()
    if action == "in":
        if shift:
            raise ClockError("You have already clocked in.")
        from .models import Location
        location = None
        if location_id:
            location = Location.objects.filter(company=locked_company, active=True, pk=location_id).first()
            if not location:
                raise ClockError("This location is not available.")
        try:
            shift = Shift.objects.create(company=locked_company, user=user, started_at=now, location=location)
        except IntegrityError:
            raise ClockError("You have already clocked in.")
        audit(locked_company, user, "clock.in", "shift:" + str(shift.pk))
        return "You are clocked in.", shift
    if not shift:
        raise ClockError("Clock in before using this action.")
    if action == "break_start":
        if shift.breaks.filter(ended_at__isnull=True).exists():
            raise ClockError("A break is already in progress.")
        BreakPeriod.objects.create(shift=shift, started_at=now)
        audit(locked_company, user, "break.start", "shift:" + str(shift.pk))
        return "Break started.", shift
    if action == "break_end":
        opened = shift.breaks.filter(ended_at__isnull=True).first()
        if not opened:
            raise ClockError("You have no active break.")
        opened.ended_at = now
        opened.save(update_fields=["ended_at"])
        audit(locked_company, user, "break.end", "shift:" + str(shift.pk))
        return "Break ended.", shift
    if now - shift.started_at > timedelta(hours=36):
        raise ClockError("This shift needs manager review before it can be closed.")
    opened = shift.breaks.filter(ended_at__isnull=True).first()
    if opened:
        opened.ended_at = now
        opened.save(update_fields=["ended_at"])
    shift.ended_at = now
    shift.save(update_fields=["ended_at"])
    audit(locked_company, user, "clock.out", "shift:" + str(shift.pk))
    return "You are clocked out.", shift
