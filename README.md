# Clinic Inventory Web App

A ready‑to‑use Clinic Inventory Management System built with Flask, HTML, and MySQL.  
This project demonstrates role‑based access, audit logging, and inventory tracking in a clean, examiner‑friendly structure.

# Features
Role‑based access control → Admin, pharmacist, and staff roles with tailored permissions.
Medicine inventory management → Track stock levels, expiry dates, and batch numbers.
Supplier management → Maintain supplier details and link them to medicines.
Dispensing records → Log medicines dispensed to patients with dates and quantities.
Notifications→ Alerts for low stock and expired medicines.
Audit logs → Record all admin actions for accountability.
Reports → Generate and view system reports (PDF export optional).
Email integration (Postmark demo) → Example helper function for transactional emails.

# Configuration
Before running the system, create your own database and update the credentials in `app.py`.  
Replace placeholders like `YOUR_DB_USER`, `YOUR_DB_PASSWORD`, and `YOUR_API_KEY_HERE` with actual values.

# Email Sending (Postmark Demo)
This project includes a helper function `send_postmark_email` that demonstrates how to send transactional emails using Postmark’s API.

# How it works:
- Builds a JSON payload with `From`, `To`, `Subject`, and `TextBody`.
- Sends the payload to Postmark’s API endpoint using your server token.
- Optionally attaches an HTML version of the email.

# Configuration:
- Replace `YOUR_POSTMARK_SERVER_TOKEN` with your own Postmark server token.
- Replace `YOUR_VERIFIED_EMAIL` with a sender email verified in your Postmark account.
- Do not commit real tokens or email addresses to GitHub.

# Flexibility:
- Adapt the same pattern for SendGrid, Mailgun, or other providers.
- Or replace with a generic SMTP function if preferred.

# Database Schema
The system uses six main tables:
- `admin_audit_log` → tracks admin actions
- `dispensed_medicines` → records dispensed medicines
- `medicine_notifications` → alerts for stock linked to suppliers and medicines
- `medicines` → core inventory
- `suppliers` → supplier details
- `users` → system users and roles

# Setup:
1. Create a new database (e.g., `clinic_inventory`).
2. Run the `schema.sql` file to generate all required tables.
3. Update `DB_CONFIG` in your code with your database credentials.  
⚠️ Table names are preserved to match code references in the project. Do not rename them unless you also update the code.

# Templates
The system uses six core HTML templates located in the `templates/` folder:
- `dashboard.html` → Main system overview with stats and notifications
- `inventory.html` → Displays medicine inventory and stock levels
- `login.html` → User login page
- `reports.html` → Generates and displays system reports
- `signup.html` → User registration page
- `suppliers.html` → Supplier management interface

# Setup
1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. Create database: `mysql -u user -p clinic_inventory < schema.sql`
4. Run: `flask run`



