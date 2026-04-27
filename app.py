import sys
from flask_apscheduler import APScheduler
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import datetime
import mysql.connector
from mysql.connector import Error
import requests

# Initialize Flask app
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "YOUR_SECRET_KEY_HERE"

# Initialize scheduler once
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# --- Database connection details ---
DB_CONFIG = {
    "host": "YOUR_DB_HOST_HERE",
    "user": "YOUR_DB_USER_HERE",
    "password": "YOUR_DB_PASSWORD_HERE",   # replace with your DB password
    "database": "YOUR_DB_NAME_HERE"
}

def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"DB connection error: {e}")
        return None

# --- Helper functions ---
def send_postmark_email(to_email, subject, text_body, html_body=None):
    url = "https://api.postmarkapp.com/email"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        # Insert your own Postmark Server Token here
        "X-Postmark-Server-Token": "YOUR_POSTMARK_SERVER_TOKEN"
    }
    data = {
        # Replace with your verified sender email in Postmark
        "From": "YOUR_VERIFIED_EMAIL",
        "To": to_email,
        "Subject": subject,
        "TextBody": text_body,
        "MessageStream": "outbound"
    }
    if html_body:
        data["HtmlBody"] = html_body

    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Postmark response: {response.status_code}, {response.text}")
        return response.status_code
    except Exception as e:
        print(f"Failed to send email via Postmark: {e}")
        return None

def get_inventory_level(quantity: int) -> str:
    if quantity == 0:
        return "Empty"
    elif 1 <= quantity <= 50:
        return "Low"
    elif 51 <= quantity <= 150:
        return "Medium"
    else:
        return "Surplus"

def compute_expiry_status(expiry_date):
    if not expiry_date:
        return "Unknown"
    today = datetime.date.today()
    try:
        if isinstance(expiry_date, datetime.date):
            return "Expired" if expiry_date < today else "Valid"
        else:
            parsed = datetime.date.fromisoformat(str(expiry_date))
            return "Expired" if parsed < today else "Valid"
    except:
        return "Unknown"

@app.route("/", methods=["GET", "POST"])
def home():
    return signup()


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        role = request.form.get("role", "user")

        if not all([username, password, email, phone]):
            flash("All fields are required.", "danger")
            return redirect(url_for("signup"))

        conn = get_connection()
        if not conn:
            flash("Database connection failed.", "danger")
            return redirect(url_for("signup"))

        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                flash("Username already exists.", "danger")
                return redirect(url_for("signup"))
            cur.execute("""
                INSERT INTO users (username, password, email, phone, user_type)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, password, email, phone, role))
            conn.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Error as e:
            flash(f"Database error: {e}", "danger")
        finally:
            cur.close()
            conn.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        conn = get_connection()
        if not conn:
            flash("Database connection failed.", "danger")
            return redirect(url_for("login"))

        try:
            cur = conn.cursor()
            cur.execute("SELECT password, user_type FROM users WHERE username=%s", (username,))
            user = cur.fetchone()
            if user and user[0] == password:
                session["username"] = username
                session["role"] = user[1]
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid username or password.", "danger")
        except Error as e:
            flash(f"Database error: {e}", "danger")
        finally:
            cur.close()
            conn.close()

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))
    return render_template("dashboard.html", username=session["username"], role=session.get("role", "user"))

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/inventory")
def inventory():
    if "username" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT m.id, m.name, m.batch_number, m.quantity, m.expiry_date,
                   s.company_name, s.id AS supplier_id
            FROM medicines m
            LEFT JOIN suppliers s ON m.supplier_id = s.id
            ORDER BY m.name ASC
        """)
        medicines = cur.fetchall()

        cur.execute("SELECT id, company_name FROM suppliers ORDER BY company_name ASC")
        suppliers = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    role = session.get("role", "").lower()
    if role == "admin":
        role = "Admin"
    elif role == "user":
        role = "User"


    for med in medicines:
        if med["expiry_date"]:
            try:
                med["expiry_date"] = med["expiry_date"].strftime("%Y-%m-%d")
            except:
                pass

    return render_template("inventory.html", medicines=medicines, suppliers=suppliers, role=role)


@app.route("/inventory/add", methods=["POST"])
def add_medicine():
    if "username" not in session:
        return redirect(url_for("login"))

    admin_user = session.get("username")
    name = request.form["name"].strip()
    batch_number = request.form["batch_number"].strip()
    quantity = int(request.form["quantity"])
    expiry_date = request.form["expiry_date"]
    supplier_id = request.form["supplier_id"]

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO medicines (name, batch_number, quantity, expiry_date, supplier_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, batch_number, quantity, expiry_date, supplier_id))
        conn.commit()

        # Notifications
        if quantity < 50:
            cur.execute("""
                INSERT INTO medicine_notifications (medicine_id, supplier_id, notified_at, status)
                VALUES (LAST_INSERT_ID(), %s, NOW(), 'notified')
                ON DUPLICATE KEY UPDATE notified_at=VALUES(notified_at), status=VALUES(status)
            """, (supplier_id,))
            conn.commit()

        # 🔑 Audit log
        details = f"Added new medicine: {name}, Batch #{batch_number}, Qty {quantity}"
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Add", "Inventory", details, "Success"))
        conn.commit()

        cur.close()
    except Exception as e:
        # Log failed attempt
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Add", "Inventory", f"Failed to add {name}", "Failed"))
        conn.commit()
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()

    flash("Medicine added successfully!", "success")
    return redirect(url_for("inventory"))


@app.route("/inventory/update/<int:med_id>", methods=["POST"])
def update_medicine(med_id):
    if "username" not in session:
        return redirect(url_for("login"))
    if session.get("role", "").lower() != "admin":
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("inventory"))

    admin_user = session.get("username")
    name = request.form.get("name")
    batch_number = request.form.get("batch_number")
    quantity = request.form.get("quantity")
    expiry_date = request.form.get("expiry_date")
    supplier_id = request.form.get("supplier_id")

    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        flash("Invalid quantity value.", "danger")
        return redirect(url_for("inventory"))

    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)

        # Fetch old record
        cur.execute("SELECT name, batch_number, quantity FROM medicines WHERE id=%s", (med_id,))
        old_med = cur.fetchone()

        # Update medicine
        cur.execute("""
            UPDATE medicines
            SET name=%s, batch_number=%s, quantity=%s, expiry_date=%s, supplier_id=%s
            WHERE id=%s
        """, (name, batch_number, quantity, expiry_date, supplier_id, med_id))
        conn.commit()

        # Notifications
        if quantity < 50:
            cur.execute("""
                INSERT INTO medicine_notifications (medicine_id, supplier_id, notified_at, status)
                VALUES (%s, %s, NOW(), 'notified')
                ON DUPLICATE KEY UPDATE notified_at=VALUES(notified_at), status=VALUES(status)
            """, (med_id, supplier_id))
        else:
            cur.execute("""
                UPDATE medicine_notifications
                SET status='restocked', restocked_at=NOW()
                WHERE medicine_id=%s AND supplier_id=%s
            """, (med_id, supplier_id))
        conn.commit()

        # 🔑 Audit log
        details = f"Edited {old_med['name']} (Batch {old_med['batch_number']}), Qty {old_med['quantity']} → {quantity}"
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Edit", "Inventory", details, "Success"))
        conn.commit()

        cur.close()
        flash("Medicine updated successfully!", "success")

    except Exception as e:
        # Log failed attempt
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Edit", "Inventory", f"Failed to edit medicine ID {med_id}", "Failed"))
        conn.commit()
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("inventory"))


@app.route("/inventory/delete/<int:med_id>", methods=["POST"])
def delete_medicine(med_id):
    if "username" not in session:
        return redirect(url_for("login"))

    admin_user = session.get("username")
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)

        # Fetch medicine before delete
        cur.execute("SELECT name, batch_number FROM medicines WHERE id=%s", (med_id,))
        med = cur.fetchone()

        # Delete medicine + notifications
        cur.execute("DELETE FROM medicines WHERE id=%s", (med_id,))
        cur.execute("DELETE FROM medicine_notifications WHERE medicine_id=%s", (med_id,))
        conn.commit()

        # 🔑 Audit log
        details = f"Deleted {med['name']}, Batch #{med['batch_number']}"
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Delete", "Inventory", details, "Success"))
        conn.commit()

        cur.close()
        flash("Medicine deleted successfully!", "info")

    except Exception as e:
        # Log failed attempt
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Delete", "Inventory", f"Failed to delete medicine ID {med_id}", "Failed"))
        conn.commit()
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("inventory"))

@app.route("/inventory/dispense", methods=["POST"])
def dispense_medicine():
    role = session.get("role")
    if not role or role.lower() != "user":
        flash("Access denied. Only Users can dispense medicine.", "danger")
        return redirect(url_for("inventory"))

    medicine_name = request.form.get("name")
    batch_number = request.form.get("batch_number")
    quantity = request.form.get("quantity")

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        flash("Invalid quantity entered.", "danger")
        return redirect(url_for("inventory"))

    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        # ✅ Fetch medicine only if BOTH name and batch_number match
        cur.execute("""
            SELECT id, batch_number, quantity, supplier_id
            FROM medicines
            WHERE name = %s AND batch_number = %s
        """, (medicine_name, batch_number))
        med = cur.fetchone()

        if not med:
            flash("Medicine with that batch number not found.", "danger")
        elif med["quantity"] < quantity:
            flash("Not enough stock available.", "danger")
        else:
            # Update stock
            cur.execute(
                "UPDATE medicines SET quantity = quantity - %s WHERE id = %s",
                (quantity, med["id"])
            )
            conn.commit()

            # Log dispense
            cur.execute("""
                INSERT INTO dispensed_medicines (name, batch_number, quantity, dispensed_by, dispense_date)
                VALUES (%s, %s, %s, %s, NOW())
            """, (medicine_name, batch_number, quantity, session.get("username")))
            conn.commit()

            flash(f"{session.get('username')} dispensed {quantity} units of {medicine_name} (Batch {batch_number}).", "success")
 # Low stock alert
            if med["quantity"] - quantity < 50:
                # Fetch updated quantity
                cur.execute("SELECT quantity, name, batch_number, supplier_id, s.company_name, s.email FROM medicines m JOIN suppliers s ON m.supplier_id = s.id WHERE m.id=%s", (med["id"],))
                updated_med = cur.fetchone()
                if updated_med:
                    subject = f"Low Stock Alert – {updated_med['name']} (Batch {updated_med['batch_number']})"
                    body = f"""
Dear {updated_med['company_name']},

Our stock of {updated_med['name']} (Batch {updated_med['batch_number']}) has dropped below 50 units.
Current quantity: {updated_med['quantity']}.

Kindly arrange for resupply at your earliest convenience.

Regards,
Pharmacy System
"""
                    html_body = body.replace("\n", "<br>")
                    response_code = send_postmark_email(updated_med["email"], subject, body, html_body)

                    # Record notification if email sent successfully
                    if response_code == 200:
                        cur.execute("""
                            INSERT INTO medicine_notifications (medicine_id, supplier_id, notified_at, status)
                            VALUES (%s, %s, NOW(), 'notified')
                            ON DUPLICATE KEY UPDATE notified_at=NOW(), status='notified'
                        """, (med["id"], updated_med["supplier_id"]))
                        conn.commit()
    except Error as e:
        flash(f"Database error: {e}", "danger")
    finally:
        try:
            cur.close()
        except:
            pass
        conn.close()

    return redirect(url_for("inventory"))

# --- Supplier Management ---
@app.route("/suppliers")
def suppliers_page():
    if "username" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    role = session.get("role")
    if not role or role.lower() != "admin":
        return render_template(
            "suppliers.html",
            suppliers=[],
            role="User",
            access_denied=True
        )

    query = request.args.get("search", "").strip()
    conn = get_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for("dashboard"))

    try:
        cur = conn.cursor(dictionary=True)
        if query:
            cur.execute("""
                SELECT id, company_name, email, phone
                FROM suppliers
                WHERE company_name LIKE %s
                ORDER BY company_name ASC
            """, (f"%{query}%",))
        else:
            cur.execute("SELECT id, company_name, email, phone FROM suppliers ORDER BY company_name ASC")
        suppliers = cur.fetchall()
        return render_template(
            "suppliers.html",
            suppliers=suppliers,
            role="Admin",
            access_denied=False,
            search=query
        )
    except Error as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for("dashboard"))
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


@app.route("/suppliers/add", methods=["POST"])
def add_supplier():
    if session.get("role", "").lower() != "admin":
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("dashboard"))

    admin_user = session.get("username")
    company_name = request.form.get("company_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    if not company_name or not email or not phone:
        flash("All fields are required.", "warning")
        return redirect(url_for("suppliers_page"))

    conn = get_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for("suppliers_page"))

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO suppliers (company_name, email, phone)
            VALUES (%s, %s, %s)
        """, (company_name, email, phone))
        conn.commit()

        # 🔑 Audit log
        details = f"Added new supplier: {company_name}"
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Add", "Supplier", details, "Success"))
        conn.commit()

        flash("Supplier added successfully!", "success")
    except Error as e:
        # Log failed attempt
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Add", "Supplier", f"Failed to add {company_name}", "Failed"))
        conn.commit()
        flash(f"Database error: {e}", "danger")
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

    return redirect(url_for("suppliers_page"))


@app.route("/suppliers/update/<int:supplier_id>", methods=["POST"])
def update_supplier(supplier_id):
    if session.get("role", "").lower() != "admin":
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("dashboard"))

    admin_user = session.get("username")
    company_name = request.form.get("company_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    if not company_name or not email or not phone:
        flash("All fields are required.", "warning")
        return redirect(url_for("suppliers_page"))

    conn = get_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for("suppliers_page"))

    try:
        cur = conn.cursor(dictionary=True)

        # Fetch old supplier
        cur.execute("SELECT company_name FROM suppliers WHERE id=%s", (supplier_id,))
        old_supplier = cur.fetchone()

        cur.execute("""
            UPDATE suppliers
            SET company_name = %s, email = %s, phone = %s
            WHERE id = %s
        """, (company_name, email, phone, supplier_id))
        conn.commit()

        # 🔑 Audit log
        details = f"Edited supplier {old_supplier['company_name']} → {company_name}"
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Edit", "Supplier", details, "Success"))
        conn.commit()

        flash("Supplier updated successfully!", "success")
    except Error as e:
        # Log failed attempt
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Edit", "Supplier", f"Failed to edit supplier ID {supplier_id}", "Failed"))
        conn.commit()
        flash(f"Database error: {e}", "danger")
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

    return redirect(url_for("suppliers_page"))


@app.route("/suppliers/delete/<int:supplier_id>", methods=["POST"])
def delete_supplier(supplier_id):
    if session.get("role", "").lower() != "admin":
        flash("Access denied. Admins only.", "danger")
        return redirect(url_for("dashboard"))

    admin_user = session.get("username")
    conn = get_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for("suppliers_page"))

    try:
        cur = conn.cursor(dictionary=True)

        # Fetch supplier before delete
        cur.execute("SELECT company_name FROM suppliers WHERE id=%s", (supplier_id,))
        supplier = cur.fetchone()

        # Delete supplier
        cur.execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))
        conn.commit()

        # Clean up notifications linked to this supplier
        cur.execute("DELETE FROM medicine_notifications WHERE supplier_id = %s", (supplier_id,))
        conn.commit()

        # 🔑 Audit log
        details = f"Deleted supplier {supplier['company_name']}"
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Delete", "Supplier", details, "Success"))
        conn.commit()

        flash("Supplier deleted successfully!", "success")
    except Error as e:
        # Log failed attempt
        cur.execute("""
            INSERT INTO admin_audit_log (admin_user, action, resource, details, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (admin_user, "Delete", "Supplier", f"Failed to delete supplier ID {supplier_id}", "Failed"))
        conn.commit()
        flash(f"Database error: {e}", "danger")
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()

    return redirect(url_for("suppliers_page"))

# --- Reports Dashboard ---
@app.route("/reports")
def reports_dashboard():
    if "username" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    role = session.get("role")
    if not role or role.lower() != "admin":
        return render_template(
            "reports.html",
            reports=[],
            role="User",
            access_denied=True
            )
    conn = get_connection()
    if not conn:
        flash("Database connection failed.", "danger")
        return redirect(url_for("dashboard"))

    try:
        cur = conn.cursor(dictionary=True)

        # Dispense log
        cur.execute("""
            SELECT name, batch_number, quantity, dispensed_by, dispense_date
            FROM dispensed_medicines
            ORDER BY dispense_date DESC
        """)
        logs = cur.fetchall()

        # 🔑 Admin Audit Log
        cur.execute("""
            SELECT admin_user, action, resource, details, status, timestamp
            FROM admin_audit_log
            ORDER BY timestamp DESC
        """)
        audits = cur.fetchall()

        # Performance stats
        cur.execute("""
            SELECT m.id, m.name, m.batch_number,
                   COALESCE(SUM(d.quantity), 0) AS total_dispensed
            FROM medicines m
            LEFT JOIN dispensed_medicines d ON m.name = d.name
            GROUP BY m.id, m.name, m.batch_number
            ORDER BY total_dispensed DESC
        """)
        stats = cur.fetchall()

        most_dispensed = [med for med in stats if med["total_dispensed"] >= 50]
        least_dispensed = [med for med in stats if med["total_dispensed"] < 50]

        # Expired medicines
        cur.execute("""
            SELECT name, batch_number, expiry_date
            FROM medicines
            WHERE expiry_date < CURDATE()
        """)
        expired = cur.fetchall()

        # Suppliers log (notifications)
        cur.execute("""
            SELECT mn.medicine_id, m.name, m.batch_number,
                   s.company_name AS supplier_name,
                   mn.status, mn.notified_at, mn.restocked_at
            FROM medicine_notifications mn
            JOIN medicines m ON mn.medicine_id = m.id
            JOIN suppliers s ON mn.supplier_id = s.id
            ORDER BY mn.notified_at DESC
        """)
        suppliers_log = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            "reports.html",
            logs=logs,
            audits=audits,              # ✅ Added here
            most_dispensed=most_dispensed,
            least_dispensed=least_dispensed,
            expired=expired,
            suppliers_log=suppliers_log,
            access_denied=False
        )

    except Error as e:
        flash(f"Database error: {e}", "danger")
        return redirect(url_for("dashboard"))

# --- Scheduler Tasks ---
def daily_low_stock_check():
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT m.id, m.name, m.batch_number, m.quantity,
                   s.id AS supplier_id, s.company_name, s.email
            FROM medicines m
            JOIN suppliers s ON m.supplier_id = s.id
            WHERE m.quantity < 50
        """)
        low_stock_meds = cur.fetchall()
        for med in low_stock_meds:
            # Always notify if stock < 50 (no suppression)
            subject = f"Low Stock Alert: {med['name']} (Batch {med['batch_number']})"
            body = (
                f"Dear {med['company_name']},\n\n"
                f"The stock for {med['name']} (Batch {med['batch_number']}) "
                f"is low. Current quantity: {med['quantity']}.\n"
                "Please resupply at your earliest convenience.\n\nRegards,\nPharmacy System"
            )
            html_body = body.replace("\n", "<br>")
            response_code = send_postmark_email(med["email"], subject, body, html_body)

            if response_code == 200:
                cur.execute("""
                    INSERT INTO medicine_notifications (medicine_id, supplier_id, notified_at, status)
                    VALUES (%s, %s, NOW(), 'notified')
                    ON DUPLICATE KEY UPDATE notified_at=NOW(), status='notified'
                """, (med["id"], med["supplier_id"]))
                conn.commit()
    except Error as e:
        print(f"Error in low stock check: {e}")
    finally:
        try:
            cur.close()
        except:
            pass
        conn.close()

# --- Scheduler Jobs ---
# Kenyan 8 AM = 12 AM EST
@scheduler.task('cron', id='low_stock_midnight_est', hour=0, minute=0, timezone='EST')
def low_stock_midnight_est():
    daily_low_stock_check()

# Kenyan 4 PM = 8 AM EST
@scheduler.task('cron', id='low_stock_morning_est', hour=8, minute=0, timezone='EST')
def low_stock_morning_est():
    daily_low_stock_check()