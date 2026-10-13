from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from core import views

urlpatterns = [
    path("healthz/", views.health, name="health"),
    path("django-admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="auth/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password-reset/", auth_views.PasswordResetView.as_view(
        template_name="auth/password_reset.html", email_template_name="auth/password_reset_email.txt",
        success_url="/accounts/password-reset/done/"), name="password_reset"),
    path("accounts/password-reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="auth/password_reset_done.html"), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="auth/password_reset_confirm.html", success_url="/accounts/reset/done/"), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(template_name="auth/password_reset_done.html"), name="password_reset_complete"),
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("verify/<str:token>/", views.verify_email, name="verify_email"),
    path("join/<str:token>/", views.accept_invite, name="accept_invite"),
    path("org/<slug:slug>/", views.dashboard, name="dashboard"),
    path("org/<slug:slug>/clock/", views.clock, name="clock"),
    path("org/<slug:slug>/team/", views.team, name="team"),
    path("org/<slug:slug>/invite/", views.invite, name="invite"),
    path("org/<slug:slug>/team/<int:membership_id>/", views.update_team, name="update_team"),
    path("org/<slug:slug>/locations/", views.locations, name="locations"),
    path("org/<slug:slug>/shifts/", views.shifts, name="shifts"),
    path("org/<slug:slug>/shifts/<int:shift_id>/", views.correct_shift, name="correct_shift"),
    path("org/<slug:slug>/leave/", views.leave, name="leave"),
    path("org/<slug:slug>/leave/<int:request_id>/review/", views.review_leave, name="review_leave"),
    path("org/<slug:slug>/reports/", views.reports, name="reports"),
    path("org/<slug:slug>/reports/export/", views.export_csv, name="export_csv"),
    path("org/<slug:slug>/audit/", views.audit, name="audit"),
    path("org/<slug:slug>/settings/", views.settings_page, name="settings"),
    path("org/<slug:slug>/billing/", views.billing, name="billing"),
    path("org/<slug:slug>/billing/checkout/", views.checkout, name="checkout"),
    path("billing/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
