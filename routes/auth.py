"""Route blueprint: generated from the legacy routes with shared dependencies."""
import os
import re
import uuid
import shutil
import zipfile
import secrets
import logging
import hmac
import json
import time
from io import BytesIO
from datetime import datetime

import MySQLdb
import pandas as pd
from flask import Blueprint, render_template, url_for, request, redirect, session, send_file, g, abort, current_app
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

import modelTrain
import recognition
from database import conn
from services.security import role_required
from services.pending_attendance import _clear_pending_attendance, _load_pending_attendance, _store_pending_attendance
from services.file_storage import unzip_file

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bp = Blueprint("PLACEHOLDER", __name__)

@bp.route("/", methods=["POST", "GET"])
def index():
    if "user" in session:  # If the user is already logged in, redirect to respective dashboard
        user_role = session.get("role")
        if user_role == "Student":
            return redirect(url_for("studentDashboard"))
        elif user_role == "Faculty":
            return redirect(url_for("faculty"))  # Redirect to Faculty dashboard
        elif user_role == "Admin":
            return redirect(url_for("admin"))  # Redirect to Admin dashboard

    if request.method == "POST":
        login_as = request.form.get("loginAs", "")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("index.html", error_msg="Please enter both username and password.")
        cursor = conn.cursor()
        authenticated = None
        must_change_password = False

        if login_as == "Student":
            cursor.execute(
                "SELECT roll_no, branch, batch, password_hash FROM student_login WHERE student_name=%s",
                (username.capitalize(),),
            )
            for roll_no, branch, batch, stored_hash in cursor.fetchall():
                valid = False
                if stored_hash:
                    try:
                        valid = check_password_hash(stored_hash, password)
                    except (ValueError, TypeError):
                        logging.warning("Invalid password hash for student %s", roll_no)
                else:
                    valid = hmac.compare_digest(str(roll_no), password)
                    if valid:
                        cursor.execute(
                            "UPDATE student_login SET password_hash=%s WHERE roll_no=%s AND password_hash IS NULL",
                            (generate_password_hash(password), roll_no),
                        )
                        conn.commit()
                        must_change_password = True
                if valid:
                    authenticated = ("Student", str(roll_no), branch, batch)
                    break

        elif login_as == "Faculty":
            cursor.execute(
                "SELECT faculty_id, password_hash FROM faculty_login WHERE BINARY faculty_name=%s",
                (username.capitalize(),),
            )
            for faculty_id, stored_hash in cursor.fetchall():
                valid = False
                if stored_hash:
                    try:
                        valid = check_password_hash(stored_hash, password)
                    except (ValueError, TypeError):
                        logging.warning("Invalid password hash for faculty %s", faculty_id)
                else:
                    valid = hmac.compare_digest(str(faculty_id), password)
                    if valid:
                        cursor.execute(
                            "UPDATE faculty_login SET password_hash=%s WHERE faculty_id=%s AND password_hash IS NULL",
                            (generate_password_hash(password), faculty_id),
                        )
                        conn.commit()
                        must_change_password = True
                if valid:
                    authenticated = ("Faculty", str(faculty_id), None, None)
                    break

        elif login_as == "Admin":
            cursor.execute(
                "SELECT password, password_hash FROM admin_login WHERE username=%s",
                (username,),
            )
            admin = cursor.fetchone()
            if admin:
                legacy_password, stored_hash = admin
                if stored_hash:
                    try:
                        valid = check_password_hash(stored_hash, password)
                    except (ValueError, TypeError):
                        valid = False
                else:
                    valid = legacy_password is not None and hmac.compare_digest(str(legacy_password), password)
                    if valid:
                        cursor.execute(
                            "UPDATE admin_login SET password_hash=%s, password=NULL WHERE username=%s AND password_hash IS NULL",
                            (generate_password_hash(password), username),
                        )
                        conn.commit()
                        must_change_password = True
                if valid:
                    authenticated = ("Admin", username, None, None)

        if not authenticated:
            return render_template("index.html", error_msg="Invalid username or password.")

        role, user_id, branch, batch = authenticated
        session.clear()
        session["user"] = user_id
        session["role"] = role
        if must_change_password:
            session["must_change_password"] = True
            return redirect(url_for("change_password"))

        if role == "Student":
            if not branch or not str(branch).strip():
                return redirect(url_for("studentReg"))
            cursor.execute(
                "SELECT COUNT(DISTINCT attendance_date) FROM attendance WHERE batch=%s AND branch=%s",
                (batch, branch),
            )
            total_classes = cursor.fetchone()[0] or 0
            cursor.execute(
                "SELECT COUNT(DISTINCT attendance_date) FROM attendance WHERE student_ID=%s AND attendance_status=%s",
                (user_id, "Present"),
            )
            present_days = cursor.fetchone()[0] or 0
            return redirect(url_for("studentDashboard", user_id=user_id, present=present_days, absent=max(0, total_classes - present_days)))
        if role == "Faculty":
            return redirect(url_for("faculty"))
        return redirect(url_for("admin"))

    return render_template("index.html")



# -------------------------------- LOGOUT FUNCTION -------------------------------- #
@bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if "user" not in session or session.get("role") not in {"Admin", "Faculty", "Student"}:
        return redirect(url_for("index"))
    if request.method == "POST":
        password = request.form.get("new_password", "")
        confirmation = request.form.get("confirm_password", "")
        if len(password) < 12 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            return render_template("change_password.html", msg="Use at least 12 characters with letters and numbers.")
        if password != confirmation:
            return render_template("change_password.html", msg="Passwords do not match.")
        password_hash = generate_password_hash(password)
        cursor = conn.cursor()
        role = session["role"]
        user_id = session["user"]
        if role == "Admin":
            cursor.execute("UPDATE admin_login SET password_hash=%s, password=NULL WHERE username=%s", (password_hash, user_id))
        elif role == "Faculty":
            cursor.execute("UPDATE faculty_login SET password_hash=%s WHERE faculty_id=%s", (password_hash, user_id))
        else:
            cursor.execute("UPDATE student_login SET password_hash=%s WHERE roll_no=%s", (password_hash, user_id))
        if cursor.rowcount != 1:
            conn.rollback()
            return render_template("change_password.html", msg="Password was not updated. Contact the administrator.")
        conn.commit()
        session.pop("must_change_password", None)
        if role == "Student":
            cursor.execute("SELECT branch FROM student_login WHERE roll_no=%s", (user_id,))
            student_row = cursor.fetchone()
            if not student_row or not student_row[0] or not str(student_row[0]).strip():
                return redirect(url_for("studentReg"))
            return redirect(url_for("studentDashboard"))
        if role == "Faculty":
            return redirect(url_for("faculty"))
        return redirect(url_for("admin"))
    return render_template("change_password.html")

@bp.route("/logout")
def logout():
    _clear_pending_attendance()
    session.clear()
    return redirect(url_for("index"))

# --------------------------------- Set Cache-Control Headers to Prevent Back Navigation ---------------------------------
