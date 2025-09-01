import os
from datetime import datetime
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import sessionmaker, declarative_base

import pandas as pd
import sqlite3

# ------------- Flask + DB setup -------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret")

DB_URL = os.environ.get("DATABASE_URL", "sqlite:///app.db")
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

# ------------- Models -------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False, default="")
    is_admin = Column(Boolean, default=False)

class TestResult(Base):
    __tablename__ = "test_results"
    id = Column(Integer, primary_key=True)
    device_no = Column(String(50), nullable=False)
    pop = Column(String(10), nullable=False)
    scratch_feinguide = Column(String(10), nullable=False)
    button_hardness = Column(String(10), nullable=False)
    button_going_inside = Column(String(10), nullable=False)
    button_on_off = Column(String(10), nullable=False)
    charging = Column(String(10), nullable=False)
    test_no = Column(String(50), nullable=False)
    test_remark = Column(Text, nullable=True, default="")
    tester_id = Column(Integer, nullable=False)
    tester_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    order_id = Column(String(50), nullable=True)  # <-- Add this line
    ndr = Column(Boolean, default=False)  # Add this line if not present

def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        # seed a default admin if not present
        if not db.query(User).filter_by(username="admin").first():
            u = User(
                username="admin",
                password_hash=generate_password_hash("admin123"),
                full_name="Administrator",
                is_admin=True,
            )
            db.add(u)
            db.commit()
            print("Seeded default admin: username=admin, password=admin123")

    # Add new column for existing databases
    try:
        conn = sqlite3.connect('app.db')
        c = conn.cursor()
        c.execute("ALTER TABLE test_results ADD COLUMN order_id TEXT")
        c.execute("ALTER TABLE test_results ADD COLUMN ndr BOOLEAN DEFAULT 0")
        conn.commit()
    except Exception as e:
        print("Error adding column:", e)
    finally:
        conn.close()

init_db()

# ------------- Helpers -------------
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    with SessionLocal() as db:
        return db.query(User).get(uid)

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

# ------------- Routes -------------
@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with SessionLocal() as db:
            user = db.query(User).filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                session["user_id"] = user.id
                session["user_name"] = user.full_name or user.username
                flash("Logged in successfully.", "success")
                return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user())

@app.route("/test/new", methods=["GET", "POST"])
@login_required
def new_test():
    if request.method == "POST":
        data = {
            "device_no": request.form.get("device_no", "").strip(),
            "pop": request.form.get("pop", "No"),
            "scratch_feinguide": request.form.get("scratch_feinguide", "No"),
            "button_hardness": request.form.get("button_hardness", "OK"),
            "button_going_inside": request.form.get("button_going_inside", "OK"),
            "button_on_off": request.form.get("button_on_off", "OK"),
            "charging": request.form.get("charging", "OK"),
            "test_no": request.form.get("test_no", "").strip(),
            "test_remark": request.form.get("test_remark", "").strip(),
            "order_id": request.form.get("order_id", "").strip(),  # <-- Add this line
        }

        user = current_user()
        # basic validation
        if not data["device_no"] or not data["test_no"]:
            flash("Device No and Test No are required.", "warning")
            return render_template("test_form.html", preset=data)

        with SessionLocal() as db:
            rec = TestResult(
                **data,
                tester_id=user.id,
                tester_name=user.full_name 
            )
            db.add(rec)
            db.commit()
            flash("Test result saved.", "success")
            # Instead of redirect, render the form again for a new test
            return render_template("test_form.html")
    return render_template("test_form.html")

@app.route("/test/edit/<int:test_id>", methods=["GET", "POST"])
@login_required
def edit_test(test_id):
    with SessionLocal() as db:
        test = db.query(TestResult).get(test_id)
        if not test:
            flash("Test record not found.", "danger")
            return redirect(url_for("list_tests"))
        if request.method == "POST":
            test.device_no = request.form.get("device_no", test.device_no)
            test.pop = request.form.get("pop", test.pop)
            test.scratch_feinguide = request.form.get("scratch_feinguide", test.scratch_feinguide)
            test.button_hardness = request.form.get("button_hardness", test.button_hardness)
            test.button_going_inside = request.form.get("button_going_inside", test.button_going_inside)
            test.button_on_off = request.form.get("button_on_off", test.button_on_off)
            test.charging = request.form.get("charging", test.charging)
            test.test_no = request.form.get("test_no", test.test_no)
            test.test_remark = request.form.get("test_remark", test.test_remark)
            test.order_id = request.form.get("order_id", test.order_id)  # <-- Add this line
            test.ndr = bool(request.form.get("ndr"))
            db.commit()
            flash("Test record updated.", "success")
            return redirect(url_for("list_tests"))
        return render_template("test_form.html", preset=test)

@app.route("/tests")
@login_required
def list_tests():
    start = request.args.get("start")
    end = request.args.get("end")
    search = request.args.get("search", "").strip()
    with SessionLocal() as db:
        q = db.query(TestResult)
        if search:
            q = q.filter(TestResult.device_no.contains(search))
        if start:
            try:
                start_dt = datetime.fromisoformat(start)
                q = q.filter(TestResult.created_at >= start_dt)
            except ValueError:
                flash("Invalid start date format. Use YYYY-MM-DD.", "warning")
        if end:
            try:
                end_dt = datetime.fromisoformat(end)
                q = q.filter(TestResult.created_at <= end_dt.replace(hour=23, minute=59, second=59))
            except ValueError:
                flash("Invalid end date format. Use YYYY-MM-DD.", "warning")
        rows = q.order_by(TestResult.created_at.desc()).all()
    return render_template("tests_list.html", rows=rows, start=start or "", end=end or "", search=search)

@app.route("/export")
@login_required
def export_excel():
    # same filters as list
    start = request.args.get("start")
    end = request.args.get("end")
    with SessionLocal() as db:
        q = db.query(TestResult)
        if start:
            try:
                start_dt = datetime.fromisoformat(start)
                q = q.filter(TestResult.created_at >= start_dt)
            except ValueError:
                pass
        if end:
            try:
                end_dt = datetime.fromisoformat(end)
                q = q.filter(TestResult.created_at <= end_dt.replace(hour=23, minute=59, second=59))
            except ValueError:
                pass
        rows = q.order_by(TestResult.created_at.desc()).all()

    # convert to DataFrame
    data = [{
        "Device No": r.device_no,
        "Order ID": r.order_id,  # <-- Add this line
        "Pop": r.pop,
        "Scratch & Feinguide": r.scratch_feinguide,
        "Buttons Hardness": r.button_hardness,
        "Button Going Inside": r.button_going_inside,
        "Button ON/OFF": r.button_on_off,
        "Charging": r.charging,
        "Test No": r.test_no,
        "Test Remark": r.test_remark,
        "NDR": "Yes" if r.ndr else "No",  # <-- Add this line
        "Tester": r.tester_name,
        "Created At (UTC)": r.created_at.strftime("%Y-%m-%d"),
    } for r in rows]

    df = pd.DataFrame(data)

    bio = BytesIO()
    df.to_excel(bio, index=False)
    bio.seek(0)
    filename = "test_results.xlsx"
    return send_file(
        bio,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ------------- Simple user management (create) -------------
@app.route("/admin/create_user", methods=["GET", "POST"])
@login_required
def create_user():
    user = current_user()
    if not user or not user.is_admin:
        flash("Admins only.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        full_name = request.form["full_name"]
        is_admin = bool(request.form.get("is_admin"))
        with SessionLocal() as db:
            if db.query(User).filter_by(username=username).first():
                flash("Username already exists.", "danger")
                return redirect(url_for("create_user"))
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),
                full_name=full_name,
                is_admin=is_admin
            )
            db.add(new_user)
            db.commit()
            flash("User created.", "success")
            return redirect(url_for("admin_users"))
    return render_template("create_user.html")

@app.route("/admin/users")
@login_required
def admin_users():
    user = current_user()
    if not user or not user.is_admin:
        flash("Admins only.", "danger")
        return redirect(url_for("dashboard"))
    with SessionLocal() as db:
        users = db.query(User).all()
    return render_template("admin_users.html", users=users)

@app.route("/admin/remove_user/<int:user_id>", methods=["POST"])
@login_required
def remove_user(user_id):
    user = current_user()
    if not user or not user.is_admin:
        flash("Admins only.", "danger")
        return redirect(url_for("dashboard"))
    with SessionLocal() as db:
        u = db.query(User).get(user_id)
        if u and not u.is_admin:
            db.delete(u)
            db.commit()
            flash("User removed.", "success")
        else:
            flash("Cannot remove admin or user not found.", "warning")
    return redirect(url_for("admin_users"))

@app.route("/admin/user_actions/<int:user_id>")
@login_required
def user_actions(user_id):
    user = current_user()
    if not user or not user.is_admin:
        flash("Admins only.", "danger")
        return redirect(url_for("dashboard"))
    selected_date = request.args.get("date")
    with SessionLocal() as db:
        u = db.query(User).get(user_id)
        q = db.query(TestResult).filter_by(tester_id=user_id)
        if selected_date:
            try:
                date_obj = datetime.fromisoformat(selected_date)
                start_dt = date_obj.replace(hour=0, minute=0, second=0)
                end_dt = date_obj.replace(hour=23, minute=59, second=59)
                q = q.filter(TestResult.created_at >= start_dt, TestResult.created_at <= end_dt)
            except ValueError:
                flash("Invalid date format. Use YYYY-MM-DD.", "warning")
        records = q.order_by(TestResult.created_at.desc()).all()
    return render_template("user_actions.html", user=u, records=records, selected_date=selected_date or "")

if __name__ == "__main__":
    # For local dev
    app.run(debug=True, host="0.0.0.0", port=5000)
