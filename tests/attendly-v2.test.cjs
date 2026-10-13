'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');

const source = fs.readFileSync(path.join(__dirname, '../v2/Code.gs'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../v2/Index.html'), 'utf8');

function makeApp() {
  let now = Date.parse('2026-10-13T08:00:00.000Z');
  class TestDate extends Date {
    constructor(...args) { super(...(args.length ? args : [now])); }
  }
  class Sheet {
    constructor(headers) { this.rows = [headers]; }
    getLastRow() { return this.rows.length; }
    appendRow(row) { this.rows.push(row.slice()); }
    getRange(row, col, rowCount = 1, colCount = 1) {
      const sheet = this;
      return {
        getValues() {
          return Array.from({length: rowCount}, (_, i) =>
            Array.from({length: colCount}, (_, j) => sheet.rows[row + i - 1][col + j - 1])
          );
        },
        setValues(values) {
          values.forEach((valuesRow, i) => valuesRow.forEach((cell, j) => {
            sheet.rows[row + i - 1][col + j - 1] = cell;
          }));
        },
        setValue(value) { sheet.rows[row - 1][col - 1] = value; }
      };
    }
  }
  const sheets = new Map([
    ['Employees v2', new Sheet(['Employee ID', 'Full Name', 'Passphrase HMAC', 'Active'])],
    ['Attendance v2', new Sheet(['Employee ID', 'Full Name', 'Start UTC ISO', 'End UTC ISO', 'Hours', 'Status', 'Work Date'])]
  ]);
  const props = new Map([['SPREADSHEET_ID','TEST_SHEET'], ['AUTH_PEPPER','unit-test-server-secret']]);
  const cache = new Map();
  let lockHeld = false;
  const ctx = {
    Date: TestDate,
    Number, String, console,
    HtmlService: {createHtmlOutputFromFile: () => ({setTitle() {return this;},addMetaTag() {return this;}})},
    Session: {getScriptTimeZone: () => 'Europe/Warsaw'},
    LockService: {getScriptLock: () => ({
      waitLock() { if (lockHeld) throw Error('locked'); lockHeld = true; },
      releaseLock() {lockHeld = false;}
    })},
    CacheService: {getScriptCache: () => ({
      get: key => cache.get(key) || null,
      put: (key,value) => cache.set(key,value),
      remove: key => cache.delete(key)
    })},
    PropertiesService: {getScriptProperties: () => ({
      getProperty: key => props.get(key) || null,
      setProperty: (key,value) => props.set(key,value)
    })},
    SpreadsheetApp: {openById: id => {
      assert.equal(id, 'TEST_SHEET');
      return {getSheetByName: name => sheets.get(name) || null, insertSheet: name => {
        const sheet = new Sheet([]);
        sheet.rows = [];
        sheet.setFrozenRows = () => {};
        sheets.set(name,sheet);
        return sheet;
      }};
    }, flush() {}},
    Utilities: {
      computeHmacSha256Signature(value, key) { return [...crypto.createHmac('sha256',key).update(value).digest()]; },
      base64Encode(value) {return Buffer.from(value).toString('base64');},
      formatDate(date,zone,pattern) {
        const formatted = new Intl.DateTimeFormat('en-GB',{
          timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',
          hour:pattern.includes('HH')?'2-digit':undefined,
          minute:pattern.includes('mm')?'2-digit':undefined,
          hourCycle:'h23'
        }).formatToParts(date).reduce((m,p)=>{m[p.type]=p.value;return m;},{});
        return formatted.year + '-' + formatted.month + '-' + formatted.day +
          (pattern.includes('HH') ? ' ' + formatted.hour + ':' + formatted.minute : '');
      },
      getUuid: () => 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    }
  };
  vm.createContext(ctx);
  vm.runInContext(source, ctx, {filename:'v2/Code.gs'});
  const employee = (id='STAFF001', name='Test Worker', passphrase='a-long-private-passphrase') =>
    ctx.provisionEmployee_(id,name,passphrase);
  const punch = (action, id='STAFF001', passphrase='a-long-private-passphrase') =>
    ctx.clockPunch({employeeId:id, passphrase, action});
  return {ctx,sheets,employee,punch,setTime: str => {now=Date.parse(str);},props};
}

test('clock in then out; server supplies accurate duration', () => {
  const app = makeApp(); app.employee();
  const first = app.punch('in');
  assert.equal(first.success,true);
  assert.match(first.message,/confirmed/i);
  app.setTime('2026-10-13T10:30:00.000Z');
  const second = app.punch('out');
  assert.equal(second.success,true);
  assert.equal(second.durationHours,2.5);
  assert.equal(app.sheets.get('Attendance v2').rows[1][5],'Completed');
});

test('duplicate clock-in and duplicate clock-out are rejected', () => {
  const app = makeApp();app.employee();
  assert.equal(app.punch('in').success,true);
  assert.equal(app.punch('in').success,false);
  assert.equal(app.sheets.get('Attendance v2').getLastRow(),2);
  app.setTime('2026-10-13T09:00:00.000Z');
  assert.equal(app.punch('out').success,true);
  assert.equal(app.punch('out').success,false);
});

test('clock-out without an open shift is rejected', () => {
  const app=makeApp();app.employee();
  assert.equal(app.punch('out').success,false);
});

test('wrong credentials never modify attendance, repeated failures are limited', () => {
  const app=makeApp();app.employee();
  for (let i=0;i<5;i++) {
    assert.equal(app.punch('in','STAFF001','wrong-secret').success,false);
  }
  assert.match(app.punch('in').message,/too many attempts/i);
  assert.equal(app.sheets.get('Attendance v2').getLastRow(),1);
});

test('overnight shifts use UTC instants and do not require same local date', () => {
  const app=makeApp();app.employee();
  app.setTime('2026-10-13T21:30:00.000Z');
  assert.equal(app.punch('in').success,true);
  app.setTime('2026-10-14T06:30:00.000Z');
  const result=app.punch('out');
  assert.equal(result.success,true);
  assert.equal(result.durationHours,9);
  assert.equal(app.sheets.get('Attendance v2').rows[1][6],'2026-10-13');
});

test('shifts exceeding 24 hours require manager review and remain open', () => {
  const app=makeApp();app.employee();
  app.punch('in');
  app.setTime('2026-10-14T12:00:00.000Z');
  assert.equal(app.punch('out').success,false);
  assert.equal(app.sheets.get('Attendance v2').rows[1][3],'');
});

test('employees must be active and employee IDs are unique', () => {
  const app=makeApp();app.employee();
  assert.throws(()=>app.employee(),/already exists/);
  app.ctx.deactivateEmployee_('STAFF001');
  assert.equal(app.punch('in').success,false);
});

test('two employees have isolated open shift state', () => {
  const app=makeApp();app.employee();
  app.employee('STAFF002','Second Worker','another-long-private-passphrase');
  assert.equal(app.punch('in').success,true);
  assert.equal(app.punch('in','STAFF002','another-long-private-passphrase').success,true);
  assert.equal(app.sheets.get('Attendance v2').getLastRow(),3);
});

test('potential spreadsheet formulas are escaped before writing', () => {
  const app=makeApp();
  app.employee('STAFF001','=SUM(A1:A2)');
  assert.match(app.sheets.get('Employees v2').rows[1][1],/^'/);
});

test('frontend only confirms server acknowledgements and does not expose DOB', () => {
  assert.match(html,/withSuccessHandler/);
  assert.match(html,/response\.success !== true/);
  assert.doesNotMatch(html,/no-cors|dateOfBirth|date of birth as a password/i);
  assert.match(source,/LockService\.getScriptLock/);
  assert.doesNotMatch(source,/YOUR_GOOGLE_SHEET_ID_HERE/);
});
