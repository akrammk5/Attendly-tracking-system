/**
 * Attendly Time Clock - Google Apps Script Backend
 * * This script handles interactions with Google Sheets for the time clock system.
 * It must be deployed as a Web App in Google Apps Script.
 * * Required Setup:
 * - A Google Sheet with two tabs: "Employee Database" and "Attendance Log"
 * - Edit permissions for the script on the target Google Sheet
 * - Deployed as a Web App with "Anyone" access
 */

// --- CONFIGURATION ---
// Replace with the ID of your Google Sheet.
const SPREADSHEET_ID = '16...........................n00';

// Sheet names used in the Google Sheet.
const EMPLOYEE_SHEET_NAME = 'Employee Database';
const ATTENDANCE_SHEET_NAME = 'Attendance Log';

// Set the timezone for date and time calculations.
// Example: 'America/New_York', 'Europe/London', 'Asia/Tokyo'
const TIMEZONE = 'Europe/Warsaw'; // Configured for Poland

/**
 * Handles GET requests. Used to fetch the employee list.
 * @param {object} e - The event parameter from the web request.
 */
function doGet(e) {
  try {
    // FIX: Check if the function is being run from the editor, where 'e' would be undefined.
    if (!e || !e.parameter) {
      return createResponse(false, 'This function is intended to be called from the web app. Running it in the editor is not a valid test.');
    }
    
    const action = e.parameter.action;
    
    if (action === 'getEmployees') {
      return getEmployees();
    }
    
    return createResponse(false, 'Unrecognized action.');
  } catch (error) {
    console.error('Error in doGet:', error.toString());
    return createResponse(false, 'Server error: ' + error.message);
  }
}

/**
 * Handles POST requests. Used to process punch-in and punch-out events.
 * @param {object} e - The event parameter from the web request.
 */
function doPost(e) {
  try {
    // It's good practice to check for postData existence as well.
    if (!e || !e.postData || !e.postData.contents) {
        return createResponse(false, 'Invalid POST request: No data received.');
    }
    const data = JSON.parse(e.postData.contents);
    
    if (data.action === 'punch') {
      return processPunch(data.employeeName, data.dateOfBirth, data.punchType);
    }
    
    return createResponse(false, 'Unrecognized action.');
  } catch (error) {
    console.error('Error in doPost:', error.toString());
    return createResponse(false, 'Server error: ' + error.message);
  }
}

/**
 * Retrieves the list of employee names from the "Employee Database" sheet.
 */
function getEmployees() {
  try {
    const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
    const employeeSheet = spreadsheet.getSheetByName(EMPLOYEE_SHEET_NAME);
    
    if (!employeeSheet) {
      throw new Error(`Sheet "${EMPLOYEE_SHEET_NAME}" not found.`);
    }
    
    const lastRow = employeeSheet.getLastRow();
    if (lastRow <= 1) {
      return createResponse(true, 'No employees found.', []);
    }
    
    const employeeRange = employeeSheet.getRange(2, 1, lastRow - 1, 1);
    const employeeData = employeeRange.getValues();
    
    const employees = employeeData
      .map(row => row[0])
      .filter(name => name && name.toString().trim() !== '');
      
    return createResponse(true, 'Employees retrieved successfully.', employees);
  } catch (error) {
    console.error('Error getting employees:', error.toString());
    return createResponse(false, 'Error retrieving employees: ' + error.message);
  }
}

/**
 * Processes a punch request (either 'in' or 'out').
 */
function processPunch(employeeName, dateOfBirth, punchType) {
  try {
    if (!employeeName || !dateOfBirth || !punchType) {
      return createResponse(false, 'Missing required parameters.');
    }
    if (punchType !== 'in' && punchType !== 'out') {
      return createResponse(false, 'Invalid punch type specified.');
    }
    
    if (!validateEmployee(employeeName, dateOfBirth)) {
      return createResponse(false, 'Employee not found or date of birth is incorrect.');
    }
    
    const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
    const attendanceSheet = spreadsheet.getSheetByName(ATTENDANCE_SHEET_NAME);
    
    if (!attendanceSheet) {
      throw new Error(`Sheet "${ATTENDANCE_SHEET_NAME}" not found.`);
    }
    
    const now = new Date();
    const currentDate = Utilities.formatDate(now, TIMEZONE, 'yyyy-MM-dd');
    const currentTime = Utilities.formatDate(now, TIMEZONE, 'HH:mm');
    
    if (punchType === 'in') {
      return processPunchIn(attendanceSheet, employeeName, currentDate, currentTime);
    } else {
      return processPunchOut(attendanceSheet, employeeName, currentDate, currentTime);
    }
    
  } catch (error) {
    console.error('Error processing punch:', error.toString());
    return createResponse(false, 'Error during processing: ' + error.message);
  }
}

/**
 * Validates an employee's name against their date of birth.
 */
function validateEmployee(employeeName, dateOfBirth) {
  try {
    const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
    const employeeSheet = spreadsheet.getSheetByName(EMPLOYEE_SHEET_NAME);
    if (!employeeSheet) return false;
    
    const lastRow = employeeSheet.getLastRow();
    if (lastRow <= 1) return false;
    
    const employeeData = employeeSheet.getRange(2, 1, lastRow - 1, 2).getValues();
    
    for (const [name, dob] of employeeData) {
      if (name && name.toString().trim() === employeeName.trim()) {
        const dobString = (dob instanceof Date) 
          ? Utilities.formatDate(dob, TIMEZONE, 'yyyy-MM-dd') 
          : dob.toString().trim();
        return dobString === dateOfBirth.trim();
      }
    }
    return false;
  } catch (error) {
    console.error('Error validating employee:', error.toString());
    return false;
  }
}

/**
 * Processes a punch-in action.
 */
function processPunchIn(attendanceSheet, employeeName, currentDate, currentTime) {
  const existingRecord = findTodayRecord(attendanceSheet, employeeName, currentDate);
  
  if (existingRecord && existingRecord.punchInTime) {
    return createResponse(false, `You have already punched in today at ${existingRecord.punchInTime}.`);
  }
  
  attendanceSheet.appendRow([employeeName, currentDate, currentTime, '', '', 'In Progress']);
  
  return createResponse(true, `Punch-in recorded successfully at ${currentTime}.`);
}

/**
 * Processes a punch-out action.
 */
function processPunchOut(attendanceSheet, employeeName, currentDate, currentTime) {
  const existingRecord = findTodayRecord(attendanceSheet, employeeName, currentDate);
  
  if (!existingRecord || !existingRecord.punchInTime) {
    return createResponse(false, 'No punch-in record found for today. Please punch in first.');
  }
  if (existingRecord.punchOutTime) {
    return createResponse(false, `You have already punched out today at ${existingRecord.punchOutTime}.`);
  }
  
  const totalHours = calculateWorkingHours(existingRecord.punchInTime, currentTime);
  const status = totalHours >= 8 ? 'On Time' : 'Less Hours';
  
  attendanceSheet.getRange(existingRecord.row, 4).setValue(currentTime);
  attendanceSheet.getRange(existingRecord.row, 5).setValue(totalHours);
  attendanceSheet.getRange(existingRecord.row, 6).setValue(status);
  
  return createResponse(true, `Punch-out recorded at ${currentTime}. Total: ${totalHours}h (${status})`);
}

/**
 * Finds today's attendance record for a specific employee.
 */
function findTodayRecord(attendanceSheet, employeeName, currentDate) {
  const lastRow = attendanceSheet.getLastRow();
  if (lastRow <= 1) return null;
  
  const attendanceData = attendanceSheet.getRange(2, 1, lastRow - 1, 6).getValues();
  
  for (let i = attendanceData.length - 1; i >= 0; i--) { // Search backwards for efficiency
    const [name, date, punchIn, punchOut] = attendanceData[i];
    
    const dateString = (date instanceof Date) 
      ? Utilities.formatDate(date, TIMEZONE, 'yyyy-MM-dd') 
      : date.toString().trim();
      
    if (name.toString().trim() === employeeName.trim() && dateString === currentDate) {
      return {
        row: i + 2,
        punchInTime: punchIn ? punchIn.toString() : '',
        punchOutTime: punchOut ? punchOut.toString() : '',
      };
    }
  }
  return null;
}

/**
 * Calculates the difference in hours between two time strings (HH:mm).
 */
function calculateWorkingHours(punchInTime, punchOutTime) {
  try {
    const [inHour, inMinute] = punchInTime.split(':').map(Number);
    const [outHour, outMinute] = punchOutTime.split(':').map(Number);
    
    const punchInDate = new Date();
    punchInDate.setHours(inHour, inMinute, 0, 0);
    
    const punchOutDate = new Date();
    punchOutDate.setHours(outHour, outMinute, 0, 0);
    
    if (punchOutDate < punchInDate) {
      punchOutDate.setDate(punchOutDate.getDate() + 1);
    }
    
    const diffMs = punchOutDate - punchInDate;
    const diffHours = diffMs / (1000 * 60 * 60);
    
    return parseFloat(diffHours.toFixed(2));
  } catch (error) {
    console.error('Error calculating hours:', error.toString());
    return 0;
  }
}

/**
 * Creates a standardized JSON response object.
 */
function createResponse(success, message, data = null) {
  const response = { success, message };
  if (data !== null) {
    response.employees = data;
  }
  return ContentService
    .createTextOutput(JSON.stringify(response))
    .setMimeType(ContentService.MimeType.JSON);
}

