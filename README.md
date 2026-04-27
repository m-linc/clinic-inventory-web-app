# clinic-inventory-web-app
ready to use clinic inventory management system built with Flask, Html and MySQL

## Configuration
Before running the system, create your own database and update the credentials.
Replace placeholders like YOUR_DB_USER, YOUR_DB_PASSWORD, and YOUR_API_KEY_HERE with actual values.

## Email Sending (Postmark)

This project includes a helper function `send_postmark_email` that demonstrates how to send transactional emails using Postmark's API.

### How it works:
- The function builds a JSON payload with `From`, `To`, `Subject`, and `TextBody`.
- It sends the payload to Postmark's API endpoint using your server token.
- If `HtmlBody` is provided, it attaches an HTML version of the email.

### Configuration:
- Replace `YOUR_POSTMARK_SERVER_TOKEN` with your own Postmark server token.
- Replace `YOUR_VERIFIED_EMAIL` with a sender email verified in your Postmark account.
- Do not commit real tokens or email addresses to GitHub.

### Flexibility:
Although this example uses Postmark, the same pattern can be adapted for other email providers:
- Change the API endpoint and headers for SendGrid, Mailgun, or other services.
- Or replace with a generic SMTP function if you prefer.

## Database Schema
The system uses six main tables:
- `admin_audit_log` → tracks admin actions
- `dispensed_medicines` → records dispensed medicines
- `medicine_notifications` → alerts for stock linked to suppliers and medicines
- `medicines` → core inventory
- `suppliers` → supplier details
- `users` → system users and roles

To set up the database:
1. Create a new database (e.g., `clinic_inventory`).
2. Run the `schema.sql` file to generate all required tables.
3. Update `DB_CONFIG` in your code with your database credentials.
⚠️ Table names are preserved to match code references in the project. Do not rename them unless you also update the code.

## Templates
The system uses six core HTML templates located in the `templates/` folder:

- `dashboard.html` → Main system overview with stats and notifications
- `inventory.html` → Displays medicine inventory and stock levels
- `login.html` → User login page
- `reports.html` → Generates and displays system reports
- `signup.html` → User registration page
- `suppliers.html` → Supplier management interface


