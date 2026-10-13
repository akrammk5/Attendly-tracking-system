# Attendly Commercial Platform (company-ready foundation)

**Release state: pre-production.** This is an original multi-company Django product under platform/, independent from the original public Google Apps Script proof of concept. It does not yet replace, migrate, or deploy the legacy app.

## Current features

| Audience | Functionality |
| --- | --- |
| Employee | Sign in, secure clock in/out, break start/end, location choice, view personal attendance, request leave |
| Manager | Role-bound dashboard, recent shifts, all company shifts, corrections with audit record, approve/reject colleagues' leave, CSV report |
| Company administrator | Manager features, invite team by time-limited email link, roles/deactivation, manage locations, activity log |
| Company owner | Company settings, trial status and company license checkout |
| Platform operator | Django staff console, health check, PostgreSQL-backed tenant records, SMTP, static assets, Stripe signed webhook |

Every management query scopes to the current authenticated company, never a globally selected user or user-supplied company ID. Database constraints prevent two simultaneous open shifts or open breaks for a given scope. Company row locks serialize punch operations in PostgreSQL. CSV cells are escaped against spreadsheet formula injection. Cross-tenant authorization tests are provided.

## Tech stack and free GitHub options

- **Django 5.2 LTS (BSD-3-Clause)**: framework with mature authentication, CSRF, ORM, accessibility-friendly HTML templates, and admin tools.
- **django-axes (MIT)**: maintained protection against brute-force login attempts. https://github.com/jazzband/django-axes
- **PostgreSQL (PostgreSQL License)**: transactional persistent database and partial unique indexes. https://github.com/postgres/postgres
- **WhiteNoise (MIT)**: deploy static frontend without a separate asset server. https://github.com/evansd/whitenoise
- **shadcn/ui (MIT)** and **Lucide (ISC)**: researched for design patterns and icon inspiration; no React libraries or third-party code were copied. https://github.com/shadcn-ui/ui and https://github.com/lucide-icons/lucide
- **Stripe Python SDK (MIT)**: official hosted checkout and signature-verified webhook. https://github.com/stripe/stripe-python
- **Custom frontend**: a high-contrast responsive employee view and administrative interface. CSS, form submissions and small progressive JavaScript; does not require React, npm, Tailwind CDN or paid templates.

No license-restricted template, GPL SaaS repository, customer data, login credentials or secret keys have been imported.

## Development setup

Prerequisites: Python 3.13, PostgreSQL for production. SQLite is supported only for local development and CI tests.

    cd platform
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    export DJANGO_DEBUG=1
    export DJANGO_SECRET_KEY=development-only-not-for-production
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py runserver

Visit /signup/ to create a sample company and its primary owner, /accounts/login/ for sign in, /django-admin/ for the platform operator console. A newly registered owner must click the signed activation link emailed to them before logging in. In local development without SMTP, Django prints the email to the server console. For employee onboarding, configure SMTP and send a secure invitation from the admin dashboard.

Automated checks:

    python manage.py check
    python manage.py makemigrations --check --dry-run
    python manage.py test core -v 2
    python manage.py collectstatic --noinput

## Real production rollout

1. Set up DNS, HTTPS, a secure proxy that overwrites X-Forwarded-Proto, and a PostgreSQL database with backups and TLS encryption. Test restore from backups.
2. Create a long unique DJANGO_SECRET_KEY in a secret manager, set DJANGO_ALLOWED_HOSTS and DJANGO_CSRF_TRUSTED_ORIGINS exactly to the HTTPS domain, and DJANGO_DEBUG=0. Read platform/.env.example.
3. Configure an actual SMTP provider: DJANGO_EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD and trusted sender domain; verify delivery and password resets. Never use console mail transport publicly.
4. Configure and verify Stripe products/prices: STRIPE_SECRET_KEY, STRIPE_PRICE_ID (one-time payment, correct currency/amount) and STRIPE_WEBHOOK_SECRET. Endpoint: https://YOUR-DOMAIN/billing/webhook/. Keep signatures secret; register checkout.session.completed, checkout.session.async_payment_succeeded, and charge.refunded. The implementation treats full verified refunds as license revocations if no other paid purchases remain; partial refunds do not revoke the license. Confirm real payment intent IDs, asynchronous methods, full/partial refund behavior, chargebacks, dispute workflows and out-of-order webhooks in Stripe test mode before going live.
5. Apply migrations separately before launch: python manage.py migrate --noinput. Collect static files. Serve with gunicorn behind HTTPS proxy; see Dockerfile and compose.yaml. The Compose example binds the web port to loopback only and does **not** supply a TLS reverse proxy.
6. Configure monitors for healthz, database, service errors and payment reconciliation. Run penetration tests, E2E UI, concurrency load tests with a real PostgreSQL instance, browser/device/accessibility audits, backup recovery drills and privacy review.
7. Publish accurate terms, privacy/cookie policy, DPA, data retention/deletion schedule, refund policy and official support contacts. Verify claims and clear whether the license is per company and how many seats are included.
8. Migrate employees and attendance from the old Google Sheet through a reviewed one-time importer (not included). Do not copy dates of birth or public legacy URLs. Reconcile totals, preserve history, notify customers, and disable the old public Apps Script deployment.
9. Email verification is required for company registration. Add sitewide signup throttling/bot controls and a cleanup task for inactive registrations before a large public launch.

## Limits and risks

- **Not yet a certified payroll or HRIS**: no automated overtime calculations, jurisdiction-specific leave accrual, schedules/rotas, holiday calendars, clock corrections that preserve historical break intervals, GPS/geofence, 2FA/SSO, PDF payslips or mobile apps.
- **Not yet a finished commercial checkout**: signed paid checkout, asynchronous payment confirmation, and full/partial refund cases are covered by mocked unit tests. Payment still requires live merchant configuration, currency/price verification, out-of-order event reconciliation, chargeback/dispute workflows, tax/invoicing, legal terms, support and real Stripe test-mode verification. Never advertise an unverified purchase as delivered.
- **Email verification**: new company owners must activate their account by clicking a time-limited emailed link. SMTP must be configured in production. Invitations also require email; production does not fall back to console mail.
- **No live deployment**: GitHub CI validates models/routes in a simulated environment; only staging testing can verify SMTP, Stripe, DB locking under concurrent traffic and real accessibility.
- The administrator correction flow retains historic break records and refuses new shift times that conflict with the break history, but still needs DST-ambiguity and manager correction UX review. Correct times only with a manager-approved process.
- Company signup sends a signed email-verification link and accounts remain inactive until confirmed. Registration still needs abuse protection, administrative tenant verification for high-risk customers, and automated cleanup of expired unverified accounts.
- Current trial seats default to 25; the paid plan seat count should be based on commercial policy and linked to a verified Stripe product.
- Audit records are application protected but database admins can alter them; immutability/export retention need infrastructure.
- PostgreSQL row locks are relied on for simultaneous punches. The development SQLite database is not a proxy for production load behavior.

## Licensing and redistribution

Attendantly's new source is independently written in this repository. Upstream framework and library dependencies retain their respective open-source licenses. Before distributing a paid software package, bundle dependency notices and decide on your own source-code license, trademark, customer terms and support entitlements.

## Related review pull requests

- Tracking proof-of-concept security improvement: #1
- Full multi-company platform: #2
- Marketing website cleanup: akrammk5/Attendly-website #1

**Never merge directly into an active production deployment before backing up data, testing a staging database, and reviewing security and business requirements.**
