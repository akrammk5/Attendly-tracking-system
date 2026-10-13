# Deploy Attendly Django staging to Vercel

Status: **NOT DEPLOYED AS A FUNCTIONING ADMIN APP** (as of 2026-10-13). Do not promote a static "READY" repository deployment: a Vercel build may succeed without serving the Django app.

## Verified host account problem
- Existing Attendly Vercel project ID: `prj_xGQNZByQUZ7pOUYLld9oxkRy5VIA`, under team `team_jNXoS0d19kaBWA8UwkEv9qPd` (`kjs-projects-78df9b1a`).
- Vercel connector reports **403 forbidden** when looking up/creating team-scoped projects. Reconnect Vercel with access to that exact team. No local Vercel CLI credentials are available to the coding agent.
- The currently linked `attendly` project has `framework: null` and **no configured environment variables**. A Git preview can show READY without a Django database.
- The existing site may be live. **Do not change its root directory**. Create a **separate** project named `attendly-platform-staging`.

## Deployment setup (owner UI steps)

1. Reconnect Vercel in ChatGPT, granting access to the team owning the existing `attendly` project. Confirm you can inspect this project in Vercel.
2. In Vercel, create a new project from GitHub repository `akrammk5/Attendly-tracking-system`. Call it `attendly-platform-staging`. **Root Directory = `platform`**, **Framework = Django**. Deploy only from reviewed branch `feat/commercial-platform-20261013` (not legacy main). Keep Vercel Authentication / deployment protection enabled.
3. Add **Neon PostgreSQL** via the project's Storage/Marketplace integrations. Use a dedicated **staging database and isolated branch**, ideally EU region near the functions. Avoid sharing a production database with previews. Ensure the integration exposes `DATABASE_URL`, with pooled connections and `sslmode=require`. This system refuses production startup without PostgreSQL.
4. Configure these variables in the **Preview** environment using Vercel's secure interface (never paste credentials into chats or commit them):
   - `DJANGO_SECRET_KEY`: a cryptographically secure, randomly generated secret unique to staging.
   - `DJANGO_DEBUG=0` 
   - `DJANGO_ALLOWED_HOSTS`: your final staging hostname; the app also validates the specific `VERCEL_URL` automatically.
   - `DJANGO_CSRF_TRUSTED_ORIGINS`: full HTTPS origin of any assigned custom staging domain.
   - `DATABASE_URL`: injected by your PostgreSQL provider.
   - `POSTGRES_SSLMODE=require`.
   - `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`, `DJANGO_EMAIL_FROM`: verified SMTP provider if you want invitation emails and customer signup; otherwise signup deliberately blocks.
   - **Leave Stripe empty** until test-mode merchant setup and signed webhook verification are complete.
5. **Run migrations separately** against the staging database before inviting anyone: from a trusted, authenticated operator environment using the same app release and database connection, run `python manage.py migrate --noinput`. **Do not put real DB passwords into commands or CI logs.** In Vercel Functions, the local filesystem is ephemeral and cannot hold a SQLite database.
6. Create a platform superuser securely: `python manage.py createsuperuser` from the authenticated operator environment. Do not check a default password into source control. Use `https://STAGING-HOST/django-admin/` for internal operator setup. Create a company plus owner membership through Django admin if SMTP has not been configured; the company admin route is `https://STAGING-HOST/org/<slug>/`.
7. Deploy staging Git branch; confirm the app serves `/healthz/` with **200 and `{"status":"ok"}`**, `/` renders the public landing, `/accounts/login/` renders the login, and `/django-admin/login/` renders Django admin.
8. Exercise login, company isolation with two tenants, staff invitations, clock in/out, breaks, manager corrections, leave approvals, CSV exports, and a verified Stripe test checkout/refund sequence; restore database snapshot in a rehearsal. Use mobile, desktop and keyboard navigation. Check runtime error logs and load testing, not only GitHub CI.
9. Configure full data protection (EU GDPR basis, retention policy, processor terms), backups, recovery and monitoring, then review a separate production deployment. Never merge into `main` or promote from preview until staging acceptance.

## Why this app needs Postgres

Attendance records, staff accounts, sessions, simultaneous punches, leave approval and payments require a durable transactional database. A serverless demo with unpersisted SQLite would silently lose or corrupt data and must not be called a working admin application.

## Vercel detection

Vercel added zero-configuration Django support in April 2026. When the Vercel project root is `platform`, Vercel detects `manage.py` and the `attendly/wsgi.py` server, and serves assets via CDN. No bespoke `api/index.py` or rewrites are required. `platform/.python-version` selects Python 3.13. Always inspect actual logs and routes rather than inferring deployment health from READY status.

Official sources:
- https://vercel.com/changelog/zero-configuration-django-support
- https://vercel.com/docs/marketplace-storage
- https://vercel.com/docs/deployments/environments
- https://vercel.com/docs/functions/runtimes/python

## Status checks still required
- Vercel team permission repaired: **NO**
- Separate staging project created: **NO**
- Dedicated staging PostgreSQL provisioned: **NO**
- Environment settings configured: **NO**
- Database migrations run: **NO**
- Real admin login manually tested: **NO**
- Production launch: **NO**
