/**
 * Attendly v2 — standalone Google Apps Script backend.
 * Deploy Code.gs + Index.html together as a Google Apps Script Web App.
 * No personal data or spreadsheet identifiers belong in source control.
 *
 * Public RPC: clockPunch(payload).
 * All administrative and internal functions end in '_' so google.script.run
 * cannot invoke them from the browser.
 */

const EMPLOYEES_TAB_ = 'Employees v2';
const ATTENDANCE_TAB_ = 'Attendance v2';
const MAX_SHIFT_HOURS_ = 24;
const FAILED_ATTEMPT_LIMIT_ = 5;
const FAILURE_WINDOW_SECONDS_ = 900;

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('Attendly | Time Clock')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/**
 * Only public RPC endpoint. All decisions and timestamps come from the server.
 * @param {{employeeId: string, passphrase: string, action: string}} payload
 * @return {{success:boolean, message:string, localTime?:string, durationHours?:number}}
 */
function clockPunch(payload) {
  if (!payload || typeof payload !== 'object') {
    return response_(false, 'Check your employee ID and passphrase.');
  }
  const id = normalizeId_(payload.employeeId);
  const passphrase = payload.passphrase;
  const action = payload.action;
  if (!id || typeof passphrase !== 'string' || passphrase.length > 128 ||
      (action !== 'in' && action !== 'out')) {
    return response_(false, 'Check your employee ID and passphrase.');
  }

  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(10000);
  } catch (error) {
    return response_(false, 'System is busy. Please try again.');
  }
  try {
    const cache = CacheService.getScriptCache();
    const lockKey = 'auth:' + id;
    const attempts = Number(cache.get(lockKey) || '0');
    if (attempts >= FAILED_ATTEMPT_LIMIT_) {
      return response_(false, 'Too many attempts. Please try again later.');
    }

    const sheet = getSheet_(EMPLOYEES_TAB_);
    const employee = findEmployee_(sheet, id);
    const isValid = employee && employee.active && safeEqual_(
      employee.hash, hashPassphrase_(id, passphrase)
    );
    if (!isValid) {
      cache.put(lockKey, String(attempts + 1), FAILURE_WINDOW_SECONDS_);
      return response_(false, 'Check your employee ID and passphrase.');
    }
    cache.remove(lockKey);

    const log = getSheet_(ATTENDANCE_TAB_);
    const now = new Date();
    const timeZone = Session.getScriptTimeZone();
    const localTime = Utilities.formatDate(now, timeZone, 'yyyy-MM-dd HH:mm');
    const workDate = Utilities.formatDate(now, timeZone, 'yyyy-MM-dd');
    const open = latestOpenShift_(log, id);
    if (action === 'in') {
      if (open) {
        return response_(false, 'You are already clocked in. Contact your manager if this is incorrect.');
      }
      log.appendRow([id, safeCell_(employee.name), now.toISOString(), '', '', 'In progress', workDate]);
      SpreadsheetApp.flush();
      return {success: true, message: 'Clock-in confirmed.', localTime: localTime};
    }
    if (!open) {
      return response_(false, 'No active shift found. Please clock in first.');
    }
    const startMs = Date.parse(open.started);
    const durationMs = now.getTime() - startMs;
    if (!Number.isFinite(startMs) || durationMs < 0 ||
        durationMs > MAX_SHIFT_HOURS_ * 60 * 60 * 1000) {
      return response_(false, 'Your shift needs a manager review. No changes were made.');
    }
    const hours = Math.round(durationMs / 36000) / 100;
    log.getRange(open.row, 4, 1, 3).setValues([[
      now.toISOString(), hours, 'Completed'
    ]]);
    SpreadsheetApp.flush();
    return {success: true, message: 'Clock-out confirmed.', localTime: localTime, durationHours: hours};
  } catch (error) {
    console.error('Attendly punch failed: ' + String(error && error.name || 'Error'));
    return response_(false, 'A server error occurred. Please contact your manager.');
  } finally {
    lock.releaseLock();
  }
}

function response_(success, message) {
  return {success: success, message: message};
}

function normalizeId_(value) {
  if (typeof value !== 'string') return '';
  const id = value.trim().toUpperCase();
  return /^[A-Z0-9_-]{3,32}$/.test(id) ? id : '';
}

function safeEqual_(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  let mismatch = a.length ^ b.length;
  const length = Math.max(a.length, b.length);
  for (let i = 0; i < length; i++) {
    mismatch |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return mismatch === 0;
}

function safeCell_(text) {
  const value = String(text || '').trim();
  return /^[=+\-@]/.test(value) ? "'" + value : value;
}

function hashPassphrase_(id, passphrase) {
  const secret = PropertiesService.getScriptProperties().getProperty('AUTH_PEPPER');
  if (!secret) throw new Error('Setup is incomplete');
  const bytes = Utilities.computeHmacSha256Signature(id + ':' + passphrase, secret);
  return Utilities.base64Encode(bytes);
}

function getSheet_(name) {
  const sheetId = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  if (!sheetId) throw new Error('Missing spreadsheet configuration');
  const sheet = SpreadsheetApp.openById(sheetId).getSheetByName(name);
  if (!sheet) throw new Error('Missing Attendly sheet: ' + name);
  return sheet;
}

function findEmployee_(sheet, id) {
  const count = sheet.getLastRow() - 1;
  if (count <= 0) return null;
  const rows = sheet.getRange(2, 1, count, 4).getValues();
  for (const row of rows) {
    if (normalizeId_(String(row[0])) === id) {
      return {name: row[1], hash: String(row[2]), active: row[3] === true};
    }
  }
  return null;
}

function latestOpenShift_(sheet, id) {
  const count = sheet.getLastRow() - 1;
  if (count <= 0) return null;
  const rows = sheet.getRange(2, 1, count, 4).getValues();
  // Check every open row. The lock serializes competing clock-in requests.
  for (let i = rows.length - 1; i >= 0; i--) {
    const row = rows[i];
    if (String(row[0]) === id && row[2] && !row[3]) {
      return {row: i + 2, started: String(row[2])};
    }
  }
  return null;
}

/**
 * ADMIN ONLY — run manually in the Apps Script editor before deployment.
 * Set SPREADSHEET_ID first in Project Settings > Script Properties.
 * Creates new tabs without changing the old system's attendance records.
 */
function setupAttendly_() {
  const props = PropertiesService.getScriptProperties();
  const spreadsheetId = props.getProperty('SPREADSHEET_ID');
  if (!spreadsheetId) throw new Error('Set SPREADSHEET_ID in Script Properties.');
  if (!props.getProperty('AUTH_PEPPER')) {
    props.setProperty('AUTH_PEPPER', Utilities.getUuid() + Utilities.getUuid() + Utilities.getUuid());
  }
  const book = SpreadsheetApp.openById(spreadsheetId);
  const definitions = [
    [EMPLOYEES_TAB_, ['Employee ID', 'Full Name', 'Passphrase HMAC', 'Active']],
    [ATTENDANCE_TAB_, ['Employee ID', 'Full Name', 'Start UTC ISO', 'End UTC ISO', 'Hours', 'Status', 'Local work date']]
  ];
  for (const entry of definitions) {
    const sheet = book.getSheetByName(entry[0]) || book.insertSheet(entry[0]);
    if (sheet.getLastRow() === 0) sheet.appendRow(entry[1]);
    sheet.setFrozenRows(1);
  }
}

/**
 * ADMIN ONLY — use from a temporary editor-only function, not an HTTP endpoint.
 * Require a unique passphrase (at least 12 characters) for each employee.
 * No plaintext credentials or dates of birth are stored in the spreadsheet.
 */
function provisionEmployee_(employeeId, fullName, passphrase) {
  const id = normalizeId_(employeeId);
  const name = typeof fullName === 'string' ? fullName.trim() : '';
  if (!id || !name || name.length > 120 ||
      typeof passphrase !== 'string' || passphrase.length < 12 || passphrase.length > 128) {
    throw new Error('Invalid ID, name, or passphrase (minimum 12 characters).');
  }
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = getSheet_(EMPLOYEES_TAB_);
    if (findEmployee_(sheet, id)) throw new Error('Employee ID already exists.');
    sheet.appendRow([id, safeCell_(name), hashPassphrase_(id, passphrase), true]);
    SpreadsheetApp.flush();
  } finally {
    lock.releaseLock();
  }
}

/** ADMIN ONLY — disable an employee without deleting historical records. */
function deactivateEmployee_(employeeId) {
  const id = normalizeId_(employeeId);
  if (!id) throw new Error('Invalid employee ID.');
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = getSheet_(EMPLOYEES_TAB_);
    const count = sheet.getLastRow() - 1;
    if (count <= 0) throw new Error('No employees found.');
    const ids = sheet.getRange(2, 1, count, 1).getValues();
    for (let i = 0; i < ids.length; i++) {
      if (normalizeId_(String(ids[i][0])) === id) {
        sheet.getRange(i + 2, 4).setValue(false);
        return;
      }
    }
    throw new Error('Employee not found.');
  } finally {
    lock.releaseLock();
  }
}
