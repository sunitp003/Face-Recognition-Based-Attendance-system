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
bp = Blueprint("student", __name__)

@bp.route("/studentReg", methods=["GET", "POST"])
@role_required("Student")
def studentReg():
    roll_id = str(session.get("user", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,15}", roll_id):
        session.clear()
        return redirect(url_for("index"))
    cursor = conn.cursor()
    cursor.execute("SELECT batch, branch FROM student_login WHERE roll_no=%s", (roll_id,))
    student = cursor.fetchone()
    if not student:
        session.clear()
        return redirect(url_for("index"))
    if student[0] and student[1]:
        return redirect(url_for("studentDashboard"))

    if request.method == "POST":
        branch = request.form.get("branch", "").strip()
        batch = request.form.get("batch", "").strip()
        zip_file = request.files.get("file")
        if not branch or not batch or not zip_file or not zip_file.filename:
            return render_template("registration.html", msg="Please fill all fields and upload a ZIP of face images.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", batch) or not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", branch):
            return render_template("registration.html", msg="Invalid batch or branch.")
        if not zip_file.filename.lower().endswith(".zip"):
            return render_template("registration.html", msg="Please upload a ZIP file.")
        target = os.path.join(APP_ROOT, "uploads", batch, branch)
        zip_dir = os.path.join(APP_ROOT, "zip_uploads")
        os.makedirs(zip_dir, exist_ok=True)
        zip_src = os.path.join(zip_dir, uuid.uuid4().hex + ".zip")
        zip_file.save(zip_src)
        try:
            extracted_folder = unzip_file(zip_src, target, roll_id)
        finally:
            if os.path.exists(zip_src):
                os.remove(zip_src)
        if not extracted_folder:
            return render_template("registration.html", msg="ZIP rejected. Upload 1–30 non-empty JPG/JPEG/PNG images, each no larger than 8 MB and 40 MB total uncompressed.")
        cursor.execute(
            "UPDATE student_login SET branch=%s, batch=%s WHERE roll_no=%s",
            (branch, batch, roll_id)
        )
        conn.commit()
        session["branch"] = branch
        session["batch"] = batch
        return redirect(url_for("studentDashboard"))
    return render_template("registration.html", msg="Enter your branch, batch and face-image ZIP.")
@bp.route("/studentDashboard", methods=["GET", "POST"])
@role_required("Student")
def studentDashboard():
    if "user" not in session:  
        return redirect(url_for("index"))

    s_ID = session["user"]
    cursor = conn.cursor()

    cursor.execute("SELECT batch, branch FROM student_login WHERE roll_no=%s;", (s_ID,))
    student_info = cursor.fetchone()

    if not student_info:
        return render_template("dashB_stud.html", msg="❌ Student record not found.")

    batch, branch = student_info  

    cursor.execute("SELECT DISTINCT subject_name FROM attendance WHERE student_ID=%s", (s_ID,))
    subjects = [row[0] for row in cursor.fetchall()]

    subject_filter = request.values.get("subject", "")
    query = "SELECT DISTINCT attendance_date FROM attendance WHERE student_ID=%s"
    params = [s_ID]

    if subject_filter:
        query += " AND subject_name=%s"
        params.append(subject_filter)

    query += " ORDER BY attendance_date"
    cursor.execute(query, tuple(params))
    dates = [d[0] for d in cursor.fetchall()]  

    if not dates:
        return render_template("dashB_stud.html", msg="⚠️ No attendance records found.", subjects=subjects)

    date_columns = [f"MAX(CASE WHEN attendance_date = '{d}' THEN attendance_status END) AS `{d}`" for d in dates]

    query = f"""
        SELECT student_ID, batch, branch, subject_name,
            {', '.join(date_columns)}, 
            ROUND((SUM(CASE WHEN attendance_status='Present' THEN 1 ELSE 0 END) / COUNT(*)) * 100, 2) AS attendance_percentage
        FROM attendance
        WHERE student_ID=%s
    """

    if subject_filter:
        query += " AND subject_name=%s"
        params.append(subject_filter)

    query += " GROUP BY student_ID, batch, branch, subject_name;"
    cursor.execute(query, tuple(params))
    result = cursor.fetchall()

    return render_template("student_view_attendance.html", result=result, dates=dates, subjects=subjects)


# --------------------------- STUDENT VIEW ATTENDANCE -------------------------- #









@bp.route("/student/view_attendance", methods=["GET", "POST"])
@role_required("Student")
def student_view_attendance():
    if "user" not in session:
        return redirect(url_for("index"))

    student_id = session["user"]
    cursor = conn.cursor()

    # ✅ Fetch student details (batch, branch)
    cursor.execute("SELECT batch, branch FROM student_login WHERE roll_no = %s", (student_id,))
    student_info = cursor.fetchone()

    if not student_info:
        return render_template("student_view_attendance.html", msg="❌ Student record not found.")

    batch, branch = student_info

    # ✅ Fetch available subjects for the student
    cursor.execute("SELECT DISTINCT subject_name FROM attendance WHERE student_ID = %s", (student_id,))
    subjects = [row[0] for row in cursor.fetchall()]

    result = []  # Initially, no attendance records
    dates = []

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        from_date = request.form.get("from", "").strip()
        to_date = request.form.get("to", "").strip()

        # ✅ Fetch distinct attendance dates
        cursor.execute("""
            SELECT DISTINCT attendance_date FROM attendance 
            WHERE student_ID=%s AND batch=%s AND branch=%s AND subject_name=%s 
            AND attendance_date BETWEEN %s AND %s
            ORDER BY attendance_date;
        """, (student_id, batch, branch, subject, from_date, to_date))
        dates = [d[0] for d in cursor.fetchall()]

        if dates:
            # ✅ Generate dynamic columns for attendance per date
            date_columns = [f"MAX(CASE WHEN attendance_date = '{d}' THEN CAST(attendance_status AS CHAR) END) AS `{d}`" for d in dates]

            # ✅ Query to fetch attendance data for the student
            query = f"""
                SELECT 
                    s.student_name, a.student_ID, a.batch, a.branch, a.year, a.subject_name,
                    {', '.join(date_columns)}, 
                    ROUND((SUM(CASE WHEN a.attendance_status='Present' THEN 1 ELSE 0 END) / COUNT(*)) * 100, 2) AS attendance_percentage
                FROM attendance a
                JOIN student_login s ON a.student_ID = s.roll_no
                WHERE a.student_ID=%s AND a.batch=%s AND a.branch=%s AND a.subject_name=%s 
                AND a.attendance_date BETWEEN %s AND %s
                GROUP BY a.student_ID, s.student_name, a.batch, a.branch, a.year, a.subject_name;
            """

            cursor.execute(query, (student_id, batch, branch, subject, from_date, to_date))
            result = cursor.fetchall()

    return render_template("student_view_attendance.html", subjects=subjects, result=result, dates=dates)









# ------------------------------------------FACULTY REGISTRATION------------------------------------------------

