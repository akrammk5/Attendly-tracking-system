from django.contrib import admin
from .models import Company, Membership, Location, Shift, BreakPeriod, LeaveRequest, Invitation, AuditEvent, Payment

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "license_active", "trial_ends_at")
    search_fields = ("name", "slug")

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("company", "user", "role", "active")
    list_filter = ("role", "active")

@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("company", "user", "started_at", "ended_at", "corrected")
    list_filter = ("company", "corrected")
    readonly_fields = ("created_at",)

@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("company", "actor", "action", "created_at")
    readonly_fields = ("company", "actor", "action", "details", "created_at")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

for model in (Location, BreakPeriod, LeaveRequest, Invitation, Payment):
    admin.site.register(model)
