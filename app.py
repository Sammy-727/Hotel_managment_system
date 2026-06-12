
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3, os, csv
from io import StringIO, BytesIO
from datetime import datetime

app = Flask(__name__)
app.secret_key = "hms-web-secret"
DB_PATH = os.path.join("instance", "hotel_web.db")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def run(sql, args=(), one=False, commit=False):
    con = db()
    cur = con.execute(sql, args)
    if commit:
        con.commit()
        last = cur.lastrowid
        con.close()
        return last
    rows = cur.fetchall()
    con.close()
    return (rows[0] if rows else None) if one else rows

def init_db():
    os.makedirs("instance", exist_ok=True)
    con = db()
    c = con.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        status TEXT DEFAULT 'Active')""")

    c.execute("""CREATE TABLE IF NOT EXISTS rooms(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_no TEXT UNIQUE,
        category TEXT,
        price REAL,
        status TEXT DEFAULT 'Available')""")

    c.execute("""CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT,
        id_proof TEXT,
        address TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS bookings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        room_id INTEGER,
        checkin TEXT,
        checkout TEXT,
        status TEXT DEFAULT 'Active')""")

    c.execute("""CREATE TABLE IF NOT EXISTS inventory(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT UNIQUE,
        category TEXT,
        quantity INTEGER,
        unit TEXT,
        price REAL,
        reorder_level INTEGER)""")

    c.execute("""CREATE TABLE IF NOT EXISTS service_usage(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER,
        item_id INTEGER,
        quantity INTEGER,
        amount REAL,
        usage_date TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS employees(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT,
        designation TEXT,
        salary REAL,
        shift TEXT,
        status TEXT DEFAULT 'Active')""")

    c.execute("""CREATE TABLE IF NOT EXISTS bills(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER UNIQUE,
        room_charges REAL,
        service_charges REAL,
        tax REAL,
        discount REAL,
        total REAL,
        payment_status TEXT,
        bill_date TEXT)""")

    con.commit()

    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        c.executemany("INSERT INTO users(username,password,role,status) VALUES(?,?,?,?)", [
            ("admin", "admin123", "Admin", "Active"),
            ("manager", "manager123", "Manager", "Active"),
            ("reception", "rec123", "Receptionist", "Active")
        ])

    if c.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
        rooms = []
        for i in range(101, 121): rooms.append((str(i), "Standard", 1500, "Available"))
        for i in range(201, 226): rooms.append((str(i), "Deluxe", 3000, "Available"))
        for i in range(301, 321): rooms.append((str(i), "Super Deluxe", 5000, "Available"))
        for i in range(401, 416): rooms.append((str(i), "Luxury", 8000, "Available"))
        for i in range(501, 506): rooms.append((str(i), "Presidential Suite", 15000, "Available"))
        c.executemany("INSERT INTO rooms(room_no,category,price,status) VALUES(?,?,?,?)", rooms)

    if c.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 0:
        c.executemany("INSERT INTO inventory(item_name,category,quantity,unit,price,reorder_level) VALUES(?,?,?,?,?,?)", [
            ("Water Bottle","Room Service",150,"pcs",30,20),
            ("Soap","Housekeeping",200,"pcs",15,30),
            ("Shampoo","Housekeeping",180,"pcs",20,30),
            ("Towel","Housekeeping",80,"pcs",150,15),
            ("Bedsheet","Housekeeping",60,"pcs",350,10),
            ("Tea Kit","Room Service",100,"pcs",50,20),
            ("Coffee Kit","Room Service",100,"pcs",70,20),
            ("Cold Drink","Restaurant",80,"bottle",60,15),
            ("Sandwich","Restaurant",50,"pcs",120,10),
            ("Dinner Thali","Restaurant",80,"plate",350,10),
            ("Laundry Service","Service",9999,"service",250,1)
        ])

    if c.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
        c.executemany("INSERT INTO employees(name,phone,email,designation,salary,shift,status) VALUES(?,?,?,?,?,?,?)", [
            ("Rohit Sharma","9876543210","rohit@hotel.com","Manager",45000,"Morning","Active"),
            ("Anita Verma","9876500001","anita@hotel.com","Receptionist",25000,"Morning","Active"),
            ("Rahul Meena","9876500002","rahul@hotel.com","Housekeeping",18000,"Evening","Active"),
            ("Pooja Singh","9876500003","pooja@hotel.com","Chef",30000,"Night","Active")
        ])

    con.commit()
    con.close()

def login_required():
    return "user_id" in session

@app.context_processor
def inject():
    return dict(current_user=session)

@app.before_request
def protect():
    allowed = ["login", "static"]
    if request.endpoint not in allowed and not login_required():
        return redirect(url_for("login"))

@app.route("/")
def index():
    return redirect(url_for("dashboard") if login_required() else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = run("SELECT * FROM users WHERE username=? AND password=? AND status='Active'",
                   (request.form["username"], request.form["password"]), one=True)
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    stats = {
        "total_rooms": run("SELECT COUNT(*) c FROM rooms", one=True)["c"],
        "available": run("SELECT COUNT(*) c FROM rooms WHERE status='Available'", one=True)["c"],
        "occupied": run("SELECT COUNT(*) c FROM rooms WHERE status='Occupied'", one=True)["c"],
        "active_bookings": run("SELECT COUNT(*) c FROM bookings WHERE status='Active'", one=True)["c"],
        "employees": run("SELECT COUNT(*) c FROM employees WHERE status='Active'", one=True)["c"],
        "revenue": run("SELECT COALESCE(SUM(total),0) t FROM bills", one=True)["t"]
    }
    room_status = run("SELECT status, COUNT(*) count FROM rooms GROUP BY status")
    low_stock = run("SELECT * FROM inventory WHERE quantity <= reorder_level")
    recent = run("""SELECT b.id,c.name,r.room_no,r.category,b.checkin,b.checkout,b.status
                    FROM bookings b JOIN customers c ON b.customer_id=c.id
                    JOIN rooms r ON b.room_id=r.id ORDER BY b.id DESC LIMIT 5""")
    return render_template("dashboard.html", stats=stats, room_status=room_status, low_stock=low_stock, recent=recent)

@app.route("/rooms")
def rooms():
    q = request.args.get("q", "")
    if q:
        rooms = run("SELECT * FROM rooms WHERE room_no LIKE ? OR category LIKE ? OR status LIKE ? ORDER BY room_no",
                    (f"%{q}%", f"%{q}%", f"%{q}%"))
    else:
        rooms = run("SELECT * FROM rooms ORDER BY room_no")
    return render_template("rooms.html", rooms=rooms, q=q)

@app.route("/rooms/add", methods=["POST"])
def add_room():
    try:
        run("INSERT INTO rooms(room_no,category,price,status) VALUES(?,?,?,?)",
            (request.form["room_no"], request.form["category"], float(request.form["price"]), request.form["status"]), commit=True)
        flash("Room added", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("rooms"))

@app.route("/rooms/update/<int:id>", methods=["POST"])
def update_room(id):
    run("UPDATE rooms SET room_no=?,category=?,price=?,status=? WHERE id=?",
        (request.form["room_no"], request.form["category"], float(request.form["price"]), request.form["status"], id), commit=True)
    flash("Room updated", "success")
    return redirect(url_for("rooms"))

@app.route("/rooms/delete/<int:id>")
def delete_room(id):
    try:
        run("DELETE FROM rooms WHERE id=?", (id,), commit=True)
        flash("Room deleted", "success")
    except:
        flash("Cannot delete linked room", "danger")
    return redirect(url_for("rooms"))

@app.route("/customers")
def customers():
    q = request.args.get("q", "")
    if q:
        customers = run("SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? ORDER BY id DESC",
                        (f"%{q}%", f"%{q}%", f"%{q}%"))
    else:
        customers = run("SELECT * FROM customers ORDER BY id DESC")
    return render_template("customers.html", customers=customers, q=q)

@app.route("/customers/add", methods=["POST"])
def add_customer():
    run("INSERT INTO customers(name,phone,email,id_proof,address) VALUES(?,?,?,?,?)",
        (request.form["name"], request.form["phone"], request.form.get("email"), request.form.get("id_proof"), request.form.get("address")), commit=True)
    return redirect(url_for("customers"))

@app.route("/customers/update/<int:id>", methods=["POST"])
def update_customer(id):
    run("UPDATE customers SET name=?,phone=?,email=?,id_proof=?,address=? WHERE id=?",
        (request.form["name"], request.form["phone"], request.form.get("email"), request.form.get("id_proof"), request.form.get("address"), id), commit=True)
    return redirect(url_for("customers"))

@app.route("/bookings")
def bookings():
    bookings = run("""SELECT b.id,c.name,r.room_no,r.category,r.price,b.checkin,b.checkout,b.status
                      FROM bookings b JOIN customers c ON b.customer_id=c.id
                      JOIN rooms r ON b.room_id=r.id ORDER BY b.id DESC""")
    customers = run("SELECT * FROM customers ORDER BY id DESC")
    rooms = run("SELECT * FROM rooms WHERE status='Available' ORDER BY room_no")
    return render_template("bookings.html", bookings=bookings, customers=customers, rooms=rooms)

@app.route("/bookings/add", methods=["POST"])
def add_booking():
    cid = request.form.get("customer_id")
    rid = request.form.get("room_id")
    checkin = request.form.get("checkin")
    checkout = request.form.get("checkout")

    if not cid or not rid or not checkin or not checkout:
        flash("Please select customer, room, check-in date and checkout date.", "danger")
        return redirect(url_for("bookings"))

    if datetime.strptime(checkout, "%Y-%m-%d") < datetime.strptime(checkin, "%Y-%m-%d"):
        flash("Checkout cannot be before check-in.", "danger")
        return redirect(url_for("bookings"))

    run("INSERT INTO bookings(customer_id,room_id,checkin,checkout,status) VALUES(?,?,?,?,?)",
        (cid, rid, checkin, checkout, "Active"), commit=True)
    run("UPDATE rooms SET status='Occupied' WHERE id=?", (rid,), commit=True)
    flash("Booking created successfully. Now you can add room service or checkout.", "success")
    return redirect(url_for("bookings"))

@app.route("/bookings/cancel/<int:id>")
def cancel_booking(id):
    b = run("SELECT * FROM bookings WHERE id=?", (id,), one=True)
    if b and b["status"] == "Active":
        run("UPDATE bookings SET status='Cancelled' WHERE id=?", (id,), commit=True)
        run("UPDATE rooms SET status='Available' WHERE id=?", (b["room_id"],), commit=True)
    return redirect(url_for("bookings"))

@app.route("/inventory")
def inventory():
    return render_template("inventory.html", inventory=run("SELECT * FROM inventory ORDER BY item_name"))

@app.route("/inventory/add", methods=["POST"])
def add_inventory():
    try:
        run("INSERT INTO inventory(item_name,category,quantity,unit,price,reorder_level) VALUES(?,?,?,?,?,?)",
            (request.form["item_name"], request.form["category"], int(request.form["quantity"]), request.form["unit"], float(request.form["price"]), int(request.form["reorder_level"])), commit=True)
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("inventory"))

@app.route("/inventory/restock/<int:id>", methods=["POST"])
def restock(id):
    run("UPDATE inventory SET quantity=quantity+? WHERE id=?", (int(request.form["quantity"]), id), commit=True)
    return redirect(url_for("inventory"))

@app.route("/service", methods=["GET", "POST"])
def service():
    if request.method == "POST":
        booking_id = request.form.get("booking_id")
        item_id = request.form.get("item_id")
        quantity = request.form.get("quantity")

        if not booking_id:
            flash("No active booking selected. First create a booking from the Bookings page.", "danger")
            return redirect(url_for("service"))
        if not item_id:
            flash("Please select an item/service.", "danger")
            return redirect(url_for("service"))
        if not quantity or int(quantity) <= 0:
            flash("Quantity must be greater than 0.", "danger")
            return redirect(url_for("service"))

        bid, iid, qty = int(booking_id), int(item_id), int(quantity)
        item = run("SELECT * FROM inventory WHERE id=?", (iid,), one=True)
        if not item:
            flash("Selected item does not exist.", "danger")
            return redirect(url_for("service"))
        if qty > item["quantity"]:
            flash("Not enough stock available.", "danger")
            return redirect(url_for("service"))

        amount = qty * item["price"]
        run("INSERT INTO service_usage(booking_id,item_id,quantity,amount,usage_date) VALUES(?,?,?,?,?)",
            (bid, iid, qty, amount, datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
        run("UPDATE inventory SET quantity=quantity-? WHERE id=?", (qty, iid), commit=True)
        flash(f"Service added successfully. Amount: ₹{amount:.2f}", "success")
        return redirect(url_for("service"))
    bookings = run("""SELECT b.id,c.name,r.room_no FROM bookings b
                      JOIN customers c ON b.customer_id=c.id JOIN rooms r ON b.room_id=r.id
                      WHERE b.status='Active' ORDER BY b.id DESC""")
    items = run("SELECT * FROM inventory ORDER BY item_name")
    usage = run("""SELECT su.id,su.booking_id,i.item_name,su.quantity,su.amount,su.usage_date
                   FROM service_usage su JOIN inventory i ON su.item_id=i.id ORDER BY su.id DESC""")
    return render_template("service.html", bookings=bookings, items=items, usage=usage)

@app.route("/billing")
def billing():
    bookings = run("""SELECT b.id,c.name,c.phone,r.room_no,r.category,r.price,b.checkin,b.checkout
                      FROM bookings b JOIN customers c ON b.customer_id=c.id
                      JOIN rooms r ON b.room_id=r.id WHERE b.status='Active' ORDER BY b.id DESC""")
    return render_template("billing.html", bookings=bookings)

@app.route("/checkout/<int:id>", methods=["POST"])
def checkout(id):
    try:
        discount = float(request.form.get("discount") or 0)
    except ValueError:
        flash("Discount must be a number.", "danger")
        return redirect(url_for("billing"))

    b = run("""SELECT b.*,c.name,c.phone,r.room_no,r.category,r.price,r.id room_id
               FROM bookings b JOIN customers c ON b.customer_id=c.id
               JOIN rooms r ON b.room_id=r.id WHERE b.id=?""", (id,), one=True)

    if not b:
        flash("Booking not found.", "danger")
        return redirect(url_for("billing"))

    days = max((datetime.strptime(b["checkout"], "%Y-%m-%d") - datetime.strptime(b["checkin"], "%Y-%m-%d")).days, 1)
    room_charges = days * b["price"]
    service_charges = run("SELECT COALESCE(SUM(amount),0) s FROM service_usage WHERE booking_id=?", (id,), one=True)["s"]
    subtotal = max(room_charges + service_charges - discount, 0)
    tax = subtotal * 0.12
    total = subtotal + tax

    try:
        run("INSERT INTO bills(booking_id,room_charges,service_charges,tax,discount,total,payment_status,bill_date) VALUES(?,?,?,?,?,?,?,?)",
            (id, room_charges, service_charges, tax, discount, total, "Paid", datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
    except Exception:
        flash("Bill already exists for this booking.", "danger")
        return redirect(url_for("billing"))

    run("UPDATE bookings SET status='Checked Out' WHERE id=?", (id,), commit=True)
    run("UPDATE rooms SET status='Cleaning' WHERE id=?", (b["room_id"],), commit=True)
    flash("Checkout completed and bill generated.", "success")
    return redirect(url_for("bill_detail", id=id))

@app.route("/bill/<int:id>")
def bill_detail(id):
    bill = run("""SELECT bills.*,c.name,c.phone,c.email,c.address,r.room_no,r.category,b.checkin,b.checkout
                  FROM bills JOIN bookings b ON bills.booking_id=b.id
                  JOIN customers c ON b.customer_id=c.id JOIN rooms r ON b.room_id=r.id
                  WHERE bills.booking_id=?""", (id,), one=True)
    services = run("""SELECT i.item_name,su.quantity,su.amount FROM service_usage su
                      JOIN inventory i ON su.item_id=i.id WHERE su.booking_id=?""", (id,))
    return render_template("bill_detail.html", bill=bill, services=services)

@app.route("/employees")
def employees():
    if session.get("role") not in ["Admin", "Manager"]:
        return redirect(url_for("dashboard"))
    return render_template("employees.html", employees=run("SELECT * FROM employees ORDER BY id DESC"))

@app.route("/employees/add", methods=["POST"])
def add_employee():
    run("INSERT INTO employees(name,phone,email,designation,salary,shift,status) VALUES(?,?,?,?,?,?,?)",
        (request.form["name"], request.form.get("phone"), request.form.get("email"), request.form.get("designation"),
         float(request.form.get("salary") or 0), request.form.get("shift"), request.form.get("status")), commit=True)
    return redirect(url_for("employees"))

@app.route("/users")
def users():
    if session.get("role") not in ["Admin", "Manager"]:
        return redirect(url_for("dashboard"))
    return render_template("users.html", users=run("SELECT id,username,role,status FROM users ORDER BY id"))

@app.route("/users/add", methods=["POST"])
def add_user():
    try:
        run("INSERT INTO users(username,password,role,status) VALUES(?,?,?,?)",
            (request.form["username"], request.form["password"], request.form["role"], request.form["status"]), commit=True)
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("users"))

@app.route("/reports")
def reports():
    bills = run("""SELECT bills.*,c.name,r.room_no FROM bills
                   JOIN bookings b ON bills.booking_id=b.id
                   JOIN customers c ON b.customer_id=c.id JOIN rooms r ON b.room_id=r.id
                   ORDER BY bills.id DESC""")
    revenue = run("SELECT COALESCE(SUM(total),0) total FROM bills", one=True)["total"]
    return render_template("reports.html", bills=bills, revenue=revenue)

@app.route("/reports/export")
def export_reports():
    rows = run("""SELECT bills.id,c.name,r.room_no,bills.room_charges,bills.service_charges,bills.tax,bills.discount,bills.total,bills.bill_date
                  FROM bills JOIN bookings b ON bills.booking_id=b.id
                  JOIN customers c ON b.customer_id=c.id JOIN rooms r ON b.room_id=r.id ORDER BY bills.id DESC""")
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Bill ID","Customer","Room","Room Charges","Service Charges","Tax","Discount","Total","Date"])
    for r in rows:
        writer.writerow([r["id"],r["name"],r["room_no"],r["room_charges"],r["service_charges"],r["tax"],r["discount"],r["total"],r["bill_date"]])
    mem = BytesIO(output.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="hms_report.csv")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
