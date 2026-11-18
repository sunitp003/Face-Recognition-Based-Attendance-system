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

@bp.route("/faculty", methods=["GET", "POST"])
@role_required("Faculty")
def faculty():
    if request.method == "POST":
        fac_id = str(session.get("user", ""))
        batch = request.form.get("batch", "").strip()
        branch = request.form.get("branch", "").strip()
        year = request.form.get("year", "").strip()
        subject = request.form.get("subject", "").strip()
        date_value = request.form.get("date", "").strip()
        upload = request.files.get("file")

        if not all((fac_id, batch, branch, year, subject, date_value)):
            return render_template(
                "dashB_faculty.html",
                msg="Please provide batch, branch, year, subject, date and video.",
                facul_id=fac_id,
            )
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", batch) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,30}", branch
        ):
            return render_template(
                "dashB_faculty.html", msg="Invalid batch or branch.", facul_id=fac_id
            )
        try:
            datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError:
            return render_template(
                "dashB_faculty.html", msg="Invalid attendance date.", facul_id=fac_id
            )
        if not upload or not upload.filename:
            return render_template(
                "dashB_faculty.html", msg="Please upload an MP4 video.", facul_id=fac_id
            )
        if not upload.filename.lower().endswith(".mp4"):
            return render_template(
                "dashB_faculty.html", msg="Only MP4 videos are supported.", facul_id=fac_id
            )

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM attendance
            WHERE attendance_date=%s AND batch=%s AND branch=%s AND subject_name=%s
            LIMIT 1
            """,
            (date_value, batch, branch, subject),
        )
        if cursor.fetchone():
            return render_template(
                "dashB_faculty.html",
                msg="Attendance already exists for this date, batch, branch and subject.",
                facul_id=fac_id,
            )

        cursor.execute(
            "SELECT roll_no FROM student_login WHERE batch=%s AND branch=%s",
            (batch, branch),
        )
        all_students = {str(row[0]) for row in cursor.fetchall()}
        if not all_students:
            return render_template(
                "dashB_faculty.html",
                msg="No registered students found for this batch and branch.",
                facul_id=fac_id,
            )

        # Use a random server-side filename; never put form values into a path.
        attendance_dir = os.path.join(APP_ROOT, "attendance")
        os.makedirs(attendance_dir, exist_ok=True)
        file_path = os.path.join(attendance_dir, f"{uuid.uuid4().hex}.mp4")
        try:
            upload.save(file_path)
            with open(file_path, "rb") as video_file:
                header = video_file.read(12)
            if len(header) < 12 or b"ftyp" not in header[4:12]:
                return render_template(
                    "dashB_faculty.html", msg="The uploaded file is not a valid MP4 video.", facul_id=fac_id
                )
            recognized = recognition.recognize_attendance(
                APP_ROOT, file_path, branch, batch
            )
            recognition_failed = recognized is None
        except Exception:
            logging.exception("Recognition processing failed")
            recognized = None
            recognition_failed = True
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

        # Detection is advisory; faculty must verify the complete list.
        recognized_students = sorted(set(map(str, recognized or [])) & all_students)
        _store_pending_attendance({
            "faculty_id": fac_id,
            "batch": batch,
            "branch": branch,
            "year": year,
            "subject": subject,
            "date": date_value,
            "suggested_present": recognized_students,
            "recognition_failed": recognition_failed,
        })
        return redirect(url_for("confirm_attendance"))

    return render_template("dashB_faculty.html", facul_id=session.get("user"))


@bp.route("/faculty/confirm_attendance", methods=["GET", "POST"])
@role_required("Faculty")
def confirm_attendance():
    pending = _load_pending_attendance()
    fac_id = str(session.get("user", ""))
    if not pending or pending.get("faculty_id") != fac_id:
        return redirect(url_for("faculty"))

    batch = pending.get("batch", "")
    branch = pending.get("branch", "")
    date_value = pending.get("date", "")
    subject = pending.get("subject", "")

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT roll_no, student_name FROM student_login
        WHERE batch=%s AND branch=%s ORDER BY roll_no
        """,
        (batch, branch),
    )
    student_rows = cursor.fetchall()
    if not student_rows:
        _clear_pending_attendance()
        return render_template(
            "dashB_faculty.html",
            msg="No registered students found. Attendance was not saved.",
            facul_id=fac_id,
        )

    if request.method == "GET":
        students = [
            {
                "roll_no": str(row[0]),
                "student_name": str(row[1]),
                "suggested": str(row[0]) in pending.get("suggested_present", []),
            }
            for row in student_rows
        ]
        return render_template(
            "attendance_review.html",
            students=students,
            batch=batch,
            branch=branch,
            subject=subject,
            attendance_date=date_value,
            detected_count=len(pending.get("suggested_present", [])),
            recognition_failed=bool(pending.get("recognition_failed")),
        )

    selected_present = set(request.form.getlist("present_ids"))
    valid_ids = {str(row[0]) for row in student_rows}
    if not selected_present.issubset(valid_ids):
        return render_template(
            "attendance_review.html",
            students=[
                {
                    "roll_no": str(row[0]),
                    "student_name": str(row[1]),
                    "suggested": str(row[0]) in pending.get("suggested_present", []),
                }
                for row in student_rows
            ],
            batch=batch,
            branch=branch,
            subject=subject,
            attendance_date=date_value,
            detected_count=len(pending.get("suggested_present", [])),
            recognition_failed=bool(pending.get("recognition_failed")),
            msg="Invalid student selection. Please review again.",
        )

    if pending.get("recognition_failed") and not selected_present:
        return render_template(
            "attendance_review.html",
            students=[
                {
                    "roll_no": str(row[0]),
                    "student_name": str(row[1]),
                    "suggested": False,
                }
                for row in student_rows
            ],
            batch=batch,
            branch=branch,
            subject=subject,
            attendance_date=date_value,
            detected_count=0,
            recognition_failed=True,
            msg="Recognition failed. Mark the present students manually before saving.",
        )

    cursor.execute(
        """
        SELECT 1 FROM attendance
        WHERE attendance_date=%s AND batch=%s AND branch=%s AND subject_name=%s
        LIMIT 1
        """,
        (date_value, batch, branch, subject),
    )
    if cursor.fetchone():
        _clear_pending_attendance()
        return render_template(
            "dashB_faculty.html",
            msg="Attendance already exists for this date, batch, branch and subject.",
            facul_id=fac_id,
        )

    try:
        conn.begin()
        for row in student_rows:
            student_id = str(row[0])
            status = "Present" if student_id in selected_present else "Absent"
            cursor.execute(
                """
                INSERT INTO attendance
                (student_ID, faculty_ID, batch, branch, year, subject_name,
                 attendance_date, attendance_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    student_id, fac_id, batch, branch, pending["year"],
                    subject, date_value, status,
                ),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"Attendance transaction failed: {exc}")
        return render_template(
            "attendance_review.html",
            students=[
                {
                    "roll_no": str(row[0]),
                    "student_name": str(row[1]),
                    "suggested": str(row[0]) in pending.get("suggested_present", []),
                }
                for row in student_rows
            ],
            batch=batch,
            branch=branch,
            subject=subject,
            attendance_date=date_value,
            detected_count=len(pending.get("suggested_present", [])),
            recognition_failed=bool(pending.get("recognition_failed")),
            msg="Attendance could not be saved. No partial records were committed.",
        )

    _clear_pending_attendance()
    msg = (
        f"Attendance confirmed and saved. Present: {len(selected_present)} "
        f"of {len(student_rows)} students."
    )
    return render_template("dashB_faculty.html", msg=msg, facul_id=fac_id)


@bp.route("/faculty/cancel_attendance_review", methods=["GET"])
@role_required("Faculty")
def cancel_attendance_review():
    session.pop("pending_attendance", None)
    return redirect(url_for("faculty"))



# -------------------------------- Faculty View Attendance  -------------------------------- #

@bp.route("/faculty/view_attendance", methods=["GET", "POST"])
@role_required("Faculty")
def faculty_view():
    if request.method == "POST":
        batch = request.form.get("batch", "").strip()
        branch = request.form.get("branch", "").strip()
        year = request.form.get("year", "").strip()
        subject = request.form.get("subject", "").strip()
        from_date = request.form.get("from", "").strip()
        to_date = request.form.get("to", "").strip()

        cursor = conn.cursor()

        # ✅ Fetch distinct attendance dates
        cursor.execute("""
            SELECT DISTINCT attendance_date FROM attendance 
            WHERE batch=%s AND branch=%s AND year=%s AND subject_name=%s 
            AND attendance_date BETWEEN %s AND %s
            ORDER BY attendance_date;
        """, (batch, branch, year, subject, from_date, to_date))
        dates = [d[0] for d in cursor.fetchall()]

        if not dates:
            return render_template("faculty_view.html", msg="⚠️ No attendance records found.")

        # ✅ Generate dynamic columns for attendance per date
        date_columns = [f"MAX(CASE WHEN attendance_date = '{d}' THEN attendance_status END) AS `{d}`" for d in dates]

        # ✅ Corrected Query with JOIN
        query = f"""
            SELECT 
                s.student_name, a.student_ID, a.batch, a.branch, a.year, a.subject_name,
                {', '.join(date_columns)}, 
                ROUND((SUM(CASE WHEN a.attendance_status='Present' THEN 1 ELSE 0 END) / COUNT(*)) * 100, 2) AS attendance_percentage
            FROM attendance a
            JOIN student_login s ON a.student_ID = s.roll_no
            WHERE a.batch=%s AND a.branch=%s AND a.year=%s AND a.subject_name=%s 
            AND a.attendance_date BETWEEN %s AND %s
            GROUP BY a.student_ID, s.student_name, a.batch, a.branch, a.year, a.subject_name;
        """

        cursor.execute(query, (batch, branch, year, subject, from_date, to_date))
        result = cursor.fetchall()

        return render_template("faculty_view.html", result=result, dates=dates)

    return render_template("faculty_view.html")






#-------------------------------  EDIT ATTENDANCE  -------------------------------------------


@bp.route("/faculty/edit_attendance", methods=["GET", "POST"])
@role_required("Faculty")
def edit_attendance():
    if request.method == "POST":
        try:
            batch = request.form.get("batch", "").strip()
            branch = request.form.get("branch", "").strip()
            year = request.form.get("year", "").strip()
            subject_name = request.form.get("subject_name", "").strip()  # ✅ Ensure correct name
            fac_id = session.get("user")  # Bind edits to the signed-in faculty member
            student_id = request.form.get("s_id", "").strip()
            status = request.form.get("status", "").strip()
            date = request.form.get("date", "").strip()
            if status not in {"Present", "Absent"}:
                return render_template("edit_att.html", msg="Invalid attendance status.")

            cursor = conn.cursor()

            # ✅ Debugging: Print Inputs
            print(f"🔎 Checking for: Student_ID={student_id}, Faculty_ID={fac_id}, Batch={batch}, Branch={branch}, Year={year}, Subject={subject_name}, Date={date}")

            # ✅ Check if attendance record exists
            query = """
                SELECT * FROM attendance 
                WHERE student_ID=%s AND faculty_ID=%s AND batch=%s 
                AND branch=%s AND year=%s AND subject_name=%s 
                AND attendance_date=%s
            """
            cursor.execute(query, (student_id, fac_id, batch, branch, year, subject_name, date))
            existing_attendance = cursor.fetchone()

            # ✅ Debugging: Print Found Records
            print(f"📋 Fetched Record: {existing_attendance}")

            if not existing_attendance:
                return render_template("edit_att.html", msg="⚠️ No attendance record found for the given details.")

            # ✅ Update Attendance Status
            update_query = """
                UPDATE attendance 
                SET attendance_status=%s 
                WHERE student_ID=%s AND faculty_ID=%s 
                AND batch=%s AND branch=%s 
                AND year=%s AND subject_name=%s 
                AND attendance_date=%s
            """
            cursor.execute(update_query, (status, student_id, fac_id, batch, branch, year, subject_name, date))
            conn.commit()

            return render_template("edit_att.html", msg="✅ Attendance Updated Successfully!")

        except Exception as e:
            conn.rollback()  # Rollback in case of error
            print(f"❌ Error: {str(e)}")  # Debugging Error
            return render_template("edit_att.html", msg=f"❌ Error: {str(e)}")

    return render_template("edit_att.html")









#------------------------------- DOWNLOAD ATTENDANCE  -------------------------------------------





@bp.route("/faculty/download_attendance", methods=["POST"])
@role_required("Faculty")
def download_attendance():
    batch = request.form.get("batch").strip()
    branch = request.form.get("branch").strip()
    year = request.form.get("year").strip()
    subject = request.form.get("subject").strip()
    from_date = request.form.get("from").strip()
    to_date = request.form.get("to").strip()

    cursor = conn.cursor()

    # ✅ Fetch distinct attendance dates
    cursor.execute("""
        SELECT DISTINCT attendance_date FROM attendance 
        WHERE batch=%s AND branch=%s AND year=%s AND subject_name=%s 
        AND attendance_date BETWEEN %s AND %s
        ORDER BY attendance_date;
    """, (batch, branch, year, subject, from_date, to_date))
    dates = [d[0] for d in cursor.fetchall()]

    if not dates:
        return render_template("faculty_view.html", msg="⚠️ No attendance records found.")

    # ✅ Generate dynamic columns for attendance per date
    date_columns = [f"MAX(CASE WHEN attendance_date = '{d}' THEN attendance_status END) AS `{d}`" for d in dates]

    # ✅ Fetch attendance data with percentage
    query = f"""
        SELECT 
            s.student_name, a.student_ID, a.batch, a.branch, a.year, a.subject_name,
            {', '.join(date_columns)}, 
            ROUND((SUM(CASE WHEN a.attendance_status='Present' THEN 1 ELSE 0 END) / COUNT(*)) * 100, 2) AS attendance_percentage
        FROM attendance a
        JOIN student_login s ON a.student_ID = s.roll_no
        WHERE a.batch=%s AND a.branch=%s AND a.year=%s AND a.subject_name=%s 
        AND a.attendance_date BETWEEN %s AND %s
        GROUP BY a.student_ID, s.student_name, a.batch, a.branch, a.year, a.subject_name;
    """

    cursor.execute(query, (batch, branch, year, subject, from_date, to_date))
    result = cursor.fetchall()

    if not result:
        return render_template("faculty_view.html", msg="⚠️ No attendance records found.")

    # ✅ Convert data to DataFrame
    columns = ["Student Name", "Student ID", "Batch", "Branch", "Year", "Subject"] + dates + ["Percentage (%)"]
    df = pd.DataFrame(result, columns=columns)

    # ✅ Append '%' symbol to Percentage column
    df["Percentage (%)"] = df["Percentage (%)"].astype(str) + "%"

    # ✅ Save to Excel
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="attendance_records.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )





# -------------------------------- ABOUT PAGE -------------------------------- #

