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
bp = Blueprint("faculty", __name__)

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
        source_mode = request.form.get("source_mode", "video").lower()

        if not all((fac_id, batch, branch, year, subject, date_value)):
            return render_template("dashB_faculty.html", msg="Please provide batch, branch, year, subject and attendance date.", facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", batch) or not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", branch):
            return render_template("dashB_faculty.html", msg="Invalid batch or branch.", facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))
        try:
            datetime.strptime(date_value, "%Y-%m-%d")
        except ValueError:
            return render_template("dashB_faculty.html", msg="Invalid attendance date.", facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))
        if source_mode not in {"photos", "video", "cctv"}:
            return render_template("dashB_faculty.html", msg="Choose a valid attendance source.", facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))

        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM attendance
            WHERE attendance_date=%s AND batch=%s AND branch=%s AND subject_name=%s
            LIMIT 1
        """, (date_value, batch, branch, subject))
        if cursor.fetchone():
            return render_template("dashB_faculty.html", msg="Attendance already exists for this date, batch, branch and subject.", facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))

        cursor.execute("SELECT roll_no FROM student_login WHERE batch=%s AND branch=%s", (batch, branch))
        all_students = {str(row[0]) for row in cursor.fetchall()}
        if not all_students:
            return render_template("dashB_faculty.html", msg="No registered students found for this batch and branch.", facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))

        recognized = None
        recognition_failed = False
        media_dir = None
        attendance_dir = os.path.join(APP_ROOT, "attendance")
        os.makedirs(attendance_dir, exist_ok=True)

        try:
            if source_mode == "cctv":
                # Camera URL is administrator-controlled and never accepted from the form.
                camera_url = os.environ.get("CCTV_RTSP_URL", "").strip()
                if not camera_url.lower().startswith("rtsp://"):
                    return render_template("dashB_faculty.html", msg="CCTV is not configured. Ask the administrator to configure CCTV_RTSP_URL.", facul_id=fac_id, cctv_enabled=False)
                try:
                    duration = int(os.environ.get("CCTV_CAPTURE_SECONDS", "300"))
                except ValueError:
                    duration = 300
                duration = max(30, min(duration, 900))
                recognized = recognition.recognize_attendance(APP_ROOT, camera_url, branch, batch, max_duration_seconds=duration)
            else:
                uploads = [item for item in request.files.getlist("files") if item and item.filename]
                # Backward compatibility for older clients posting the original file field.
                if not uploads:
                    legacy_upload = request.files.get("file")
                    if legacy_upload and legacy_upload.filename:
                        uploads = [legacy_upload]
                if not uploads:
                    return render_template("dashB_faculty.html", msg="Select at least one photo or one video to upload.", facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))

                if source_mode == "photos":
                    if len(uploads) > 30 or any(os.path.splitext(item.filename)[1].lower() not in {".jpg", ".jpeg", ".png"} for item in uploads):
                        return render_template("dashB_faculty.html", msg="Upload up to 30 JPG, JPEG or PNG photos at a time.", facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))
                elif len(uploads) != 1 or os.path.splitext(uploads[0].filename)[1].lower() != ".mp4":
                    return render_template("dashB_faculty.html", msg="Upload exactly one MP4 video for video mode.", facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))

                media_dir = os.path.join(attendance_dir, uuid.uuid4().hex)
                os.makedirs(media_dir, exist_ok=False)
                saved_paths = []
                total_bytes = 0
                for index, upload in enumerate(uploads, start=1):
                    extension = os.path.splitext(secure_filename(upload.filename))[1].lower()
                    destination = os.path.join(media_dir, f"upload_{index}{extension}")
                    upload.save(destination)
                    size = os.path.getsize(destination)
                    total_bytes += size
                    if size == 0 or size > 50 * 1024 * 1024 or total_bytes > 50 * 1024 * 1024:
                        raise ValueError("Uploads must be non-empty and total no more than 50 MB.")
                    saved_paths.append(destination)

                if source_mode == "photos":
                    recognized = recognition.recognize_attendance_images(APP_ROOT, saved_paths, branch, batch)
                else:
                    with open(saved_paths[0], "rb") as video_file:
                        header = video_file.read(12)
                    if len(header) < 12 or b"ftyp" not in header[4:12]:
                        raise ValueError("The uploaded file is not a valid MP4 video.")
                    try:
                        video_limit = int(os.environ.get("VIDEO_MAX_DURATION_SECONDS", "900"))
                    except ValueError:
                        video_limit = 900
                    video_limit = max(30, min(video_limit, 900))
                    recognized = recognition.recognize_attendance(
                        APP_ROOT, saved_paths[0], branch, batch,
                        max_duration_seconds=video_limit,
                    )

            recognition_failed = recognized is None
        except ValueError as exc:
            return render_template("dashB_faculty.html", msg=str(exc), facul_id=fac_id, cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))
        except Exception:
            logging.exception("Attendance source processing failed")
            recognized = None
            recognition_failed = True
        finally:
            if media_dir and os.path.isdir(media_dir):
                shutil.rmtree(media_dir, ignore_errors=True)

        # Recognition is advisory. The teacher checks every student before saving.
        recognized_students = sorted(set(map(str, recognized or [])) & all_students)
        _store_pending_attendance({
            "faculty_id": fac_id,
            "batch": batch,
            "branch": branch,
            "year": year,
            "subject": subject,
            "date": date_value,
            "source_mode": source_mode,
            "suggested_present": recognized_students,
            "recognition_failed": recognition_failed,
        })
        return redirect(url_for("confirm_attendance"))

    return render_template("dashB_faculty.html", facul_id=session.get("user"), cctv_enabled=bool(os.environ.get("CCTV_RTSP_URL")))


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
    # Clear the server-side pending review record and its backing file.
    _clear_pending_attendance()
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

