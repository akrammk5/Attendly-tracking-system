/**
 * Attendly Time Clock - Google Apps Script Backend
 *
 * This script handles interactions with Google Sheets for the time clock system.
 * It must be deployed as a Web App within Google Apps Script.
 *
 * Required Setup:
 * - A Google Sheet with two tabs: "Employee Database" and "Attendance Log"
 * - Write permissions for the script on the Google Sheet.
 * - Deployed as a Web App with "Anyone" access.
 */

// --- Configuration ---
// IMPORTANT: Replace with the ID of your Google Sheet.
const SPREADSHEET_ID = 'YOUR_GOOGLE_SHEET_ID_HERE';

const EMPLOYEE_SHEET_NAME = 'Employee Database';
const ATTENDANCE_SHEET_NAME = 'Attendance Log';

// Set the timezone for all date and time calculations.
// Example: 'America/New_York', 'Europe/London', 'Asia/Tokyo'
const TIMEZONE = 'GMT+0'; 
const STANDARD_WORK_HOURS = 8; // Standard hours for "On Time" status calculation.

/**
 * Handles GET requests. Used to fetch the employee list.
 */
function doGet(e) {
  try {
    const action = e.parameter.action;
    if (action === 'getEmployees') {
      return getEmployees();
    }
    return createJsonResponse(false, 'Unrecognized action');
  } catch (error) {
    Logger.log(`doGet Error: ${error.message}`);
    return createJsonResponse(false, `Server error: ${error.message}`);
  }
}

/**
 * Handles POST requests. Used to process punch-in and punch-out events.
 */
function doPost(e) {
  try {
    // Need to parse the postData contents as it's a stringified JSON
    const data = JSON.parse(e.postData.contents);
    
    if (data.action === 'punch') {
      return processPunch(data.employeeName, data.dateOfBirth, data.punchType);
    }
    
    return createJsonResponse(false, 'Unrecognized action');
  } catch (error) {
    Logger.log(`doPost Error: ${error.message}`);
    return createJsonResponse(false, `Server error: ${error.message}`);
  }
}

/**
 * Fetches the list of employee names from the "Employee Database" sheet.
 */
function getEmployees() {
  try {
    const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
    const employeeSheet = spreadsheet.getSheetByName(EMPLOYEE_SHEET_NAME);
    
    if (!employeeSheet) throw new Error(`Sheet "${EMPLOYEE_SHEET_NAME}" not found.`);
    
    const lastRow = employeeSheet.getLastRow();
    if (lastRow <= 1) return createJsonResponse(true, 'No employees found.', []);
    
    const employeeData = employeeSheet.getRange(2, 1, lastRow - 1, 1).getValues();
    const employees = employeeData.map(row => row[0]).filter(name => name && name.toString().trim() !== '');
    
    return createJsonResponse(true, 'Employees retrieved successfully.', employees);
  } catch (error) {
    Logger.log(`getEmployees Error: ${error.message}`);
    return createJsonResponse(false, `Error retrieving employees: ${error.message}`);
  }
}

/**
 * Processes a punch-in or punch-out request.
 */
function processPunch(employeeName, dateOfBirth, punchType) {
  try {
    if (!employeeName || !dateOfBirth || !punchType) {
      return createJsonResponse(false, 'Missing required parameters.');
    }
    if (punchType !== 'in' && punchType !== 'out') {
      return createJsonResponse(false, 'Invalid punch type.');
    }
    if (!validateEmployee(employeeName, dateOfBirth)) {
      return createJsonResponse(false, 'Employee not found or date of birth is incorrect.');
    }

    const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
    const attendanceSheet = spreadsheet.getSheetByName(ATTENDANCE_SHEET_NAME);
    if (!attendanceSheet) throw new Error(`Sheet "${ATTENDANCE_SHEET_NAME}" not found.`);

    const now = new Date();
    const currentDate = Utilities.formatDate(now, TIMEZONE, 'yyyy-MM-dd');
    const currentTime = Utilities.formatDate(now, TIMEZONE, 'HH:mm');

    return punchType === 'in'
      ? processPunchIn(attendanceSheet, employeeName, currentDate, currentTime)
      : processPunchOut(attendanceSheet, employeeName, currentDate, currentTime);
      
  } catch (error) {
    Logger.log(`processPunch Error: ${error.message}`);
    return createJsonResponse(false, `Error processing punch: ${error.message}`);
  }
}

/**
 * Validates that an employee exists and their date of birth matches.
 */
function validateEmployee(employeeName, dateOfBirth) {
  try {
    const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
    const employeeSheet = spreadsheet.getSheetByName(EMPLOYEE_SHEET_NAME);
    if (!employeeSheet) return false;

    const employeeData = employeeSheet.getRange(2, 1, employeeSheet.getLastRow() - 1, 2).getValues();
    
    for (const row of employeeData) {
      const [name, dob] = row;
      if (name && name.toString().trim() === employeeName.trim()) {
        const dobString = (dob instanceof Date)
          ? Utilities.formatDate(dob, TIMEZONE, 'yyyy-MM-dd')
          : dob.toString().trim();
        return dobString === dateOfBirth.trim();
      }
    }
    return false;
  } catch (error) {
    Logger.log(`validateEmployee Error: ${error.message}`);
    return false;
  }
}

/**
 * Processes a punch-in event.
 */
function processPunchIn(attendanceSheet, employeeName, currentDate, currentTime) {
  const existingRecord = findTodayRecord(attendanceSheet, employeeName, currentDate);
  if (existingRecord && existingRecord.punchInTime) {
    return createJsonResponse(false, `You already punched in today at ${existingRecord.punchInTime}.`);
  }
  
  // Columns: Employee Name | Date | Punch In Time | Punch Out Time | Total Hours | Status
  attendanceSheet.appendRow([employeeName, currentDate, currentTime, '', '', 'In Progress']);
  
  return createJsonResponse(true, `Punch-in successful at ${currentTime}.`);
}

/**
 * Processes a punch-out event.
 */
function processPunchOut(attendanceSheet, employeeName, currentDate, currentTime) {
  const existingRecord = findTodayRecord(attendanceSheet, employeeName, currentDate);
  
  if (!existingRecord || !existingRecord.punchInTime) {
    return createJsonResponse(false, 'No punch-in record found for today. Please punch in first.');
  }
  if (existingRecord.punchOutTime) {
    return createJsonResponse(false, `You already punched out today at ${existingRecord.punchOutTime}.`);
  }

  const totalHours = calculateWorkingHours(existingRecord.punchInTime, currentTime);
  const status = totalHours >= STANDARD_WORK_HOURS ? 'On Time' : 'Less Hours';
  
  // Update the existing row
  attendanceSheet.getRange(existingRecord.row, 4).setValue(currentTime); // Punch Out Time
  attendanceSheet.getRange(existingRecord.row, 5).setValue(totalHours);  // Total Hours
  attendanceSheet.getRange(existingRecord.row, 6).setValue(status);       // Status
  
  return createJsonResponse(true, `Punch-out successful at ${currentTime}. Total hours: ${totalHours.toFixed(2)} (${status})`);
}

/**
 * Finds today's attendance record for a specific employee.
 */
function findTodayRecord(attendanceSheet, employeeName, currentDate) {
  const lastRow = attendanceSheet.getLastRow();
  if (lastRow < 2) return null;

  const data = attendanceSheet.getRange(2, 1, lastRow - 1, 6).getValues();
  
  // Iterate backwards to find the most recent entry first
  for (let i = data.length - 1; i >= 0; i--) {
    const [name, date] = data[i];
    const dateString = (date instanceof Date) 
      ? Utilities.formatDate(date, TIMEZONE, 'yyyy-MM-dd')
      : date.toString();
      
    if (name.toString().trim() === employeeName.trim() && dateString === currentDate) {
      return {
        row: i + 2, // +2 because data range starts at row 2
        punchInTime: data[i][2] ? data[i][2].toString() : '',
        punchOutTime: data[i][3] ? data[i][3].toString() : '',
      };
    }
  }
  return null;
}

/**
 * Calculates the total working hours between two times (HH:mm format).
 */
function calculateWorkingHours(punchInTime, punchOutTime) {
  try {
    const [inHour, inMinute] = punchInTime.split(':').map(Number);
    const [outHour, outMinute] = punchOutTime.split(':').map(Number);
    
    const punchIn = new Date();
    punchIn.setHours(inHour, inMinute, 0, 0);
    
    const punchOut = new Date();
    punchOut.setHours(outHour, outMinute, 0, 0);
    
    if (punchOut < punchIn) punchOut.setDate(punchOut.getDate() + 1); // Handles overnight shifts
    
    const diffMs = punchOut - punchIn;
    const diffHours = diffMs / (1000 * 60 * 60);
    
    return parseFloat(diffHours.toFixed(2));
  } catch (error) {
    Logger.log(`calculateWorkingHours Error: ${error.message}`);
    return 0;
  }
}

/**
 * Creates a standardized JSON response for the Web App.
 */
function createJsonResponse(success, message, data = null) {
  const response = { success, message };
  if (data !== null) {
    // Standardize the data key based on content
    response[Array.isArray(data) ? 'employees' : 'data'] = data;
  }
  
  return ContentService
    .createTextOutput(JSON.stringify(response))
    .setMimeType(ContentService.MimeType.JSON);
}


/**
 * UTILITY FUNCTION: Sets up the Google Sheet with required tabs and headers.
 * Run this function once from the script editor to prepare your sheet.
 */
function initializeSheet() {
  try {
    const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
    
    // Employee Database Sheet
    let employeeSheet = spreadsheet.getSheetByName(EMPLOYEE_SHEET_NAME);
    if (!employeeSheet) employeeSheet = spreadsheet.insertSheet(EMPLOYEE_SHEET_NAME);
    employeeSheet.getRange('A1:B1').setValues([['Employee Name', 'DOB (YYYY-MM-DD)']]).setFontWeight('bold');
    // Add sample data
    employeeSheet.getRange('A2:B5').setValues([
      ['John Doe', '1985-03-15'],
      ['Jane Smith', '1990-07-22'],
      ['Peter Jones', '1988-11-08'],
      ['Mary Williams', '1992-01-30']
    ]);
    
    // Attendance Log Sheet
    let attendanceSheet = spreadsheet.getSheetByName(ATTENDANCE_SHEET_NAME);
    if (!attendanceSheet) attendanceSheet = spreadsheet.insertSheet(ATTENDANCE_SHEET_NAME);
    attendanceSheet.getRange('A1:F1').setValues([['Employee Name', 'Date', 'Punch In Time', 'Punch Out Time', 'Total Hours', 'Status']]).setFontWeight('bold');
    
    // Formatting
    attendanceSheet.getRange('B:B').setNumberFormat('yyyy-mm-dd');
    attendanceSheet.getRange('C:D').setNumberFormat('hh:mm');
    attendanceSheet.getRange('E:E').setNumberFormat('0.00');
    attendanceSheet.setFrozenRows(1);
    employeeSheet.setFrozenRows(1);
    
    Logger.log('Sheets initialized successfully.');
    return 'Sheets initialized successfully.';
  } catch (error) {
    Logger.log(`Initialization Error: ${error.message}`);
    return `Error: ${error.message}`;
  }
}
