from flask import Flask, render_template, url_for, request, redirect,flash, jsonify, json,session
from functools import wraps
from werkzeug.utils import secure_filename
import re
import uuid
from flask_session import Session
from flask_login import logout_user
from flask_ngrok import run_with_ngrok
from dataset_prepare import face_detect #Dataset_prepare.py
import modelTrain  # modelTrain.py
import os
import MySQLdb
import pymysql

import pandas as pd
from flask import send_file

import shutil
import zipfile
import recognition #recognition.py
import secrets
import openpyxl

app = Flask(__name__)

# Secure secret key for session management
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Define project root
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

def role_required(*allowed_roles):
    """Protect routes using the authenticated role in the session."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") not in allowed_roles or "user" not in session:
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


# Database connection
conn = MySQLdb.connect(
    host=os.environ.get("DB_HOST", "127.0.0.1"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", ""),
    db=os.environ.get("DB_NAME", "attendance_database1"),
)
conn.autocommit(on=True)






# ---------------------------------HOMEPAGE---------------------------------------------------------
@app.route("/", methods=["POST", "GET"])
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
        loginAs = request.values.get("loginAs")
        username = request.values.get("username").strip()
        password = request.values.get("password").strip()
        cursor = conn.cursor()

        if loginAs == "Student":
            username_cap = username.capitalize()
            cursor.execute("SELECT branch, batch FROM student_login WHERE student_name=%s AND roll_no=%s;", 
                           (username_cap, password))
            student = cursor.fetchone()

            if student:
                branch, batch = student
                session["user"] = password  # Store roll number in session
                session["role"] = "Student"  # Store role

                if not branch or branch.strip() == "":
                    return redirect(url_for("studentReg"))

                cursor.execute("SELECT COUNT(DISTINCT attendance_date) FROM attendance WHERE batch=%s AND branch=%s;", 
                               (batch, branch))
                total_classes = cursor.fetchone()[0] or 0

                cursor.execute("SELECT COUNT(DISTINCT attendance_date) FROM attendance WHERE student_ID=%s AND attendance_status='Present';", 
                               [password])
                present_days = cursor.fetchone()[0] or 0

                absent_days = total_classes - present_days
                return redirect(url_for('studentDashboard', user_id=password, present=present_days, absent=absent_days))
            else:
                return render_template("index.html", error_msg="❌ Invalid Username or Password")

        elif loginAs == "Faculty":
           # cursor.execute("SELECT * FROM faculty_login WHERE faculty_id=%s;", [username])
            cursor.execute("SELECT * FROM faculty_login WHERE binary faculty_name=%s AND binary faculty_id=%s;",(username.capitalize(),password))
            faculty = cursor.fetchone()

            # if faculty:
            #     session["user"] = username
            #     session["role"] = "Faculty"  # Store faculty role
            #     return redirect(url_for("faculty"))  # Redirect to Faculty Dashboard
            # else:
            #     return render_template("index.html", error_msg="❌ Invalid Faculty ID")
            if faculty:
                print(f"✅ Faculty ID {username} found!")
                session["user"] = username  # Store faculty ID in session
                session["role"] = "Faculty"  # Store role as Faculty
                return redirect(url_for("faculty"))  # Redirect to Faculty Dashboard
            else:
                print(f"❌ Faculty ID {username} not found.")
                return render_template("index.html", error_msg="❌ Invalid Faculty ID")











        elif loginAs == "Admin":
            cursor.execute("SELECT * FROM admin_login WHERE username=%s AND password=%s;", (username, password))
            admin = cursor.fetchone()

            if admin:
                session["user"] = username
                session["role"] = "Admin"  # Store admin role
                return redirect(url_for("admin"))  # Redirect to Admin Dashboard
            else:
                return render_template("index.html", error_msg="❌ Invalid Admin Credentials")

    return render_template("index.html")



# -------------------------------- LOGOUT FUNCTION -------------------------------- #
@app.route("/logout")
def logout():
    session.clear()  # ✅ Clears session data
    return redirect(url_for("index"))

# --------------------------------- Set Cache-Control Headers to Prevent Back Navigation ---------------------------------
@app.after_request
def set_response_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response










# ----------------------------- ADMIN DASHBOARD ----------------------------- #

@app.route("/admin/", methods=["POST", "GET"])
@role_required("Admin")
def admin():
    if request.method == "POST":
        batch = request.values.get("batch").strip()
        branch = request.values.get("branch").strip()
        if batch and branch:
            ret = modelTrain.TrainImages(APP_ROOT, batch, branch)
            msg = "Model Trained Successfully" if ret == 1 else "No images found!"
        else:
            msg = "Please provide batch and branch."
        return render_template("dashB_admin.html", msg=msg)
    return render_template("dashB_admin.html")

@app.route("/admin/delete", methods=["POST", "GET"])
@role_required("Admin")
def deleteStudent():
    if request.method == "POST":
        entity = request.values.get("remove_id").strip()
        roll_id = request.values.get("id").strip()
        cursor = conn.cursor()
        if entity == "Student":
            cursor.execute("DELETE FROM student_login WHERE BINARY roll_no=%s", [roll_id])
        elif entity == "Faculty":
            cursor.execute("DELETE FROM faculty_login WHERE BINARY faculty_id=%s", [roll_id])
        else:
            return render_template("admin_remove.html", msg="Invalid entity type.")

        conn.commit()
        msg = f"Successfully removed {roll_id}"
        return render_template("admin_remove.html", msg=msg)

    return render_template("admin_remove.html")

@app.route("/admin/addRecord", methods=["POST", "GET"])
@role_required("Admin")
def addRecord():
    if request.method == "POST":
        entity = request.values.get("add_id").strip()
        username = request.values.get("username").strip().capitalize()
        password = request.values.get("password").strip()
        cursor = conn.cursor()

        try:
            if entity == "Student":
                cursor.execute("INSERT INTO student_login (student_name, roll_no, branch, batch) VALUES (%s, %s, '', '')", (username, password))
                conn.commit()
                msg = "Added Student Login Successfully"
            elif entity == "Faculty":
                cursor.execute("INSERT INTO faculty_login (faculty_name, faculty_id, department) VALUES (%s, %s, '')", (username, password))
                conn.commit()
                msg = "Added Faculty Login Successfully"
            else:
                msg = "Invalid entity type."
        except pymysql.IntegrityError:
            msg = "This record is already in the database"

        return render_template("admin_add.html", msg=msg)

    return render_template("admin_add.html")











# --------------------------- STUDENT REGISTRATION -------------------------- #


# def unzip_file(zip_src, dst_dir, roll_id):
    """Safely extract a bounded set of image files for one student."""
    if not zipfile.is_zipfile(zip_src):
        return None
    extract_to = os.path.join(dst_dir, str(roll_id))
    os.makedirs(extract_to, exist_ok=True)
    allowed = (".jpg", ".jpeg", ".png")
    total_bytes = 0
    saved = 0
    try:
        with zipfile.ZipFile(zip_src, "r") as archive:
            for item in archive.infolist():
                if item.is_dir():
                    continue
                filename = secure_filename(os.path.basename(item.filename))
                if not filename or not filename.lower().endswith(allowed):
                    continue
                if item.file_size > 8 * 1024 * 1024:
                    continue
                total_bytes += item.file_size
                if total_bytes > 40 * 1024 * 1024 or saved >= 200:
                    break
                destination = os.path.join(extract_to, filename)
                with archive.open(item) as source, open(destination, "wb") as target:
                    shutil.copyfileobj(source, target)
                saved += 1
    except (zipfile.BadZipFile, OSError):
        return None
    return extract_to if saved else None









def unzip_file(zip_src, dst_dir, roll_id):
    """Safely extract a bounded set of image files for one student."""
    if not zipfile.is_zipfile(zip_src):
        return None
    extract_to = os.path.join(dst_dir, str(roll_id))
    os.makedirs(extract_to, exist_ok=True)
    allowed = (".jpg", ".jpeg", ".png")
    total_bytes = 0
    saved = 0
    try:
        with zipfile.ZipFile(zip_src, "r") as archive:
            for item in archive.infolist():
                if item.is_dir():
                    continue
                filename = secure_filename(os.path.basename(item.filename))
                if not filename or not filename.lower().endswith(allowed):
                    continue
                if item.file_size > 8 * 1024 * 1024:
                    continue
                total_bytes += item.file_size
                if total_bytes > 40 * 1024 * 1024 or saved >= 200:
                    break
                destination = os.path.join(extract_to, filename)
                with archive.open(item) as source, open(destination, "wb") as target:
                    shutil.copyfileobj(source, target)
                saved += 1
    except (zipfile.BadZipFile, OSError):
        return None
    return extract_to if saved else None
@app.route("/studentReg", methods=["GET", "POST"])
@role_required("Student")
def studentReg():
    roll_id = str(session.get("user", ""))
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
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", batch) or not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", branch):
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
            return render_template("registration.html", msg="No valid JPG/PNG images found in the ZIP.")
        cursor.execute(
            "UPDATE student_login SET branch=%s, batch=%s WHERE roll_no=%s",
            (branch, batch, roll_id)
        )
        conn.commit()
        session["branch"] = branch
        session["batch"] = batch
        return redirect(url_for("studentDashboard"))
    return render_template("registration.html", msg="Enter your branch, batch and face-image ZIP.")
@app.route("/studentDashboard", methods=["GET", "POST"])
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









@app.route("/student/view_attendance", methods=["GET", "POST"])
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

@app.route("/faculty", methods=["GET", "POST"])
@role_required("Faculty")
def faculty():
    if request.method == "POST":
        fac_id = session.get("user")  # Trust only the authenticated faculty identity
        batch = request.values.get("batch")
        branch = request.values.get("branch")
        year = request.values.get("year")
        subject = request.values.get("subject")
        date = request.values.get("date")
        upload = request.files.get("file")

        cursor = conn.cursor()

        # ✅ Check if attendance already recorded for this date
        cursor.execute("""
            SELECT * FROM attendance 
            WHERE attendance_date=%s AND batch=%s AND branch=%s AND subject_name=%s
        """, (date, batch, branch, subject))
        existing_attendance = cursor.fetchall()

        if existing_attendance:
            print(f"⚠️ Attendance already recorded for {date}, batch: {batch}, branch: {branch}, subject: {subject}")
            return render_template("dashB_faculty.html", msg="⚠️ Attendance already uploaded for this date.", facul_id=fac_id)

        # ✅ Save uploaded attendance video file
        if upload:
            filename = f"{batch}_{branch}_{subject}_{date}.mp4"
            file_path = os.path.join(APP_ROOT, "attendance", filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)  # Ensure directory exists
            upload.save(file_path)

            print(f"📂 File uploaded successfully: {file_path}")

            # ✅ Recognize faces from the video
            recognized_students = recognition.recognize_attendance(APP_ROOT, file_path, branch, batch)

            if recognized_students:
                print(f"✅ Recognized Students: {recognized_students}")
            else:
                print("No confident face matches; attendance was not written.")
                return render_template("dashB_faculty.html", msg="❌ No confident faces recognized. Attendance NOT saved; check the video/model and retry.", facul_id=fac_id)

            # ✅ Fetch all registered students for batch & branch
            cursor.execute("SELECT roll_no FROM student_login WHERE batch=%s AND branch=%s", (batch, branch))
            all_students = [str(row[0]) for row in cursor.fetchall()]  # Convert all student IDs to strings

            print(f"📋 Total Registered Students: {len(all_students)} -> {all_students}")

            # ✅ Convert recognized IDs to string for correct comparison
            recognized_students = set(str(Id) for Id in recognized_students)

            # ✅ Insert or update attendance records
            for student_id in all_students:
                status = "Present" if str(student_id) in recognized_students else "Absent"
                
                cursor.execute("""
                    INSERT INTO attendance (student_ID, faculty_ID, batch, branch, year, subject_name, attendance_date, attendance_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE attendance_status = VALUES(attendance_status);
                """, (student_id, fac_id, batch, branch, year, subject, date, status))

            conn.commit()
            msg = "✅ Attendance saved successfully!"
            print(msg)
            return render_template("dashB_faculty.html", msg=msg, facul_id=fac_id)

    return render_template("dashB_faculty.html", facul_id=request.args.get("facul_id"))






# -------------------------------- Faculty View Attendance  -------------------------------- #

@app.route("/faculty/view_attendance", methods=["GET", "POST"])
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


@app.route("/faculty/edit_attendance", methods=["GET", "POST"])
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





@app.route("/faculty/download_attendance", methods=["POST"])
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
    file_path = "attendance_records.xlsx"
    df.to_excel(file_path, index=False)

    # ✅ Send file as download
    return send_file(file_path, as_attachment=True)





# -------------------------------- ABOUT PAGE -------------------------------- #

@app.route("/about")
def about():
    return render_template("About.html")

# -------------------------------- MAIN FUNCTION -------------------------------- #

if __name__ == "__main__":
    app.run(debug=True)
