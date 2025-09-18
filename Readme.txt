Attendly - Smart Time Clock System
Attendly is a complete, modern time clock system designed for small businesses. It features a sleek, futuristic user interface and a powerful backend that runs entirely on your free Google account, eliminating monthly fees and ensuring you have 100% control over your own data.

Key Features
Futuristic UI: A modern, responsive interface that looks great on any device (desktop, tablet, or mobile).

Secure Validation: Employees validate their identity using their name and date of birth—no passwords to forget.

Automated Calculations: Automatically calculates total work hours (e.g., 8.50) and determines employee status.

Smart Status: Automatically assigns a status like "On Time" or "Less Hours" based on your defined work hours.

Duplicate Prevention: Smart logic prevents employees from punching in or out multiple times accidentally, ensuring clean data.

Data Ownership: All your attendance data is stored securely in a Google Sheet that you own and control. We never see your data.

Zero Recurring Fees: The system runs on the free infrastructure of Google Sheets and Google Apps Script. Buy it once, own it forever.

How It Works
The system is composed of two main parts:

Frontend (index.html): A self-contained HTML file that provides the user interface. Employees interact with this page to punch in and out. It can be hosted for free on services like GitHub Pages or Netlify.

Backend (google-apps-script.js): A Google Apps Script that connects to your Google Sheet. It handles all the logic, such as validating employees, recording punches, and calculating hours. You deploy this as a private Web App in your own Google account.

The frontend sends requests to the backend, which securely processes the data and updates your Google Sheet in real-time.

System Requirements
A standard, free Google Account.

A modern web browser (Chrome, Firefox, Safari, Edge).

An internet connection.

Getting Started
To get your Attendly system up and running, please follow the detailed instructions in the DEPLOYMENT_GUIDE.md. The setup process involves three main phases:

Configure Google Sheets: Create a new Google Sheet and set up two tabs for your employee list and attendance log.

Deploy Google Apps Script: Deploy the backend script as a Web App within your Google account and get a unique URL.

Configure the Frontend: Paste your unique Web App URL into the index.html file.

The entire setup process typically takes about 15-20 minutes.