# Attendly v2 — secure time clock (review before production)

This opt-in upgrade addresses serious problems in the original static frontend and public Google Apps Script endpoint. **It does not modify the current deployment or historical attendance data.** The legacy files remain in this repository during migration.

## What changed

- Server-confirmed punch results via google.script.run: no more no-cors false success.
- Employee ID and a private passphrase replace public employee listing and dates of birth.
- ScriptLock prevents duplicate shifts from concurrent requests.
- UTC timestamps and open-shift lookup correctly handle overnight shifts and daylight-saving transitions.
- Work time is calculated from actual elapsed milliseconds, not HH:mm wall-clock strings.
- Generic error messages, basic best-effort attempt throttling and spreadsheet formula escaping.
- Responsive, accessible, dependency-free employee interface with reduced-motion support.

## Deployment — do this in a NEW Apps Script project

1. Make an owner-controlled **backup** of the existing Google Sheet. Do not share employee data publicly.
2. In Google Apps Script create a new project, configure the project time zone (for example Europe/Warsaw).
3. Add the project Script Property **SPREADSHEET_ID** with your actual Google Sheet ID. Never publish the ID, credentials or secret values in GitHub.
4. Put v2/Code.gs in Code.gs and create a Google Apps Script HTML file **named Index**, copying in v2/Index.html.
5. Run **setupAttendly_** manually from the Apps Script editor with owner permissions. It initializes two NEW tabs, Employees v2 and Attendance v2, without editing the old tabs.
6. Add staff using a temporary, editor-only setup function that calls **provisionEmployee_** with a unique employee ID and unique 12+ character secret passphrase. Example:

       function temporarySetup_() {
         provisionEmployee_('STAFF001', 'Example Person', 'a-unique-secret-passphrase');
       }

   Run the temporary function once and **delete it before publishing**. Keep credentials out of the spreadsheet, repository and logs; give each employee their own passphrase through a secure channel.
7. Deploy a NEW web app: execute as **Me**. Choose an access restriction appropriate to your company. If anonymous staff have no Google sign-in, deployment may require Anyone; unlike v1, the browser can neither enumerate employees nor punch without a passphrase.
8. Open the new Apps Script Web App URL, not the GitHub Pages HTML preview. Use a test employee for wrong passphrase, clock in, duplicate clock in, clock out, duplicate clock out; verify the resulting sheet.
9. After verifying the v2 deployment, **retire and disable the older publicly accessible v1 Google Apps Script web app** and time-clock link. Keep v1 attendance records read-only for historical/audit purposes.

To disable a staff member, run **deactivateEmployee_('STAFF001')** from a temporary, editor-only function. For credential rotation, disable the previous ID and create a new one until an owner-approved rotation workflow is built.

## Data and privacy

Employees v2: Employee ID, Full Name, Passphrase HMAC, Active. No DOB or plaintext passphrases.
Attendance v2: Employee ID, Full Name, Start UTC ISO, End UTC ISO, Duration Hours, Status, Local work date.

The time clock uses server time. The Apps Script project time zone controls the local date/time displayed. Only one shift can remain open per employee; shifts longer than 24 hours require manager correction rather than silently recording implausible hours.

## Remaining limitations — required for a commercial rollout

- **Controlled pilot only**: the CacheService attempt limit is best effort and cannot guarantee brute-force protection. Use high-entropy long passphrases. For wider usage, use strong identity or Workspace SSO, durable rate limiting and administrative audit trails.
- Staff can clock remotely using the right credentials; on-site attendance validation is not included.
- No break, split-shift, leave, overtime, work-policy configuration, payroll or manual correction UI.
- No admin dashboard, automated secret rotation, monitoring, retention enforcement, backups or recovery.
- Google Sheets/Apps Script quotas can limit capacity. Validate operational volume and Google Workspace access permissions.
- Review applicable data protection and employment requirements before processing real worker records.
- **Legacy files are intentionally unchanged and remain insecure**; do not onboard new employees with them.

## Local tests

Run in any Node.js 20+ environment:

    node --test tests/attendly-v2.test.cjs

The test suite simulates Apps Script services. It cannot prove real deployment permissions, quotas or production browser behavior. A manual staging test is mandatory.
