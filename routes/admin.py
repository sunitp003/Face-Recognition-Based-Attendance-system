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
bp = Blueprint("admin", __name__)

@bp.route("/admin/", methods=["POST", "GET"])
@role_required("Admin")
def admin():
    if request.method == "POST":
        batch = request.values.get("batch", "").strip()
        branch = request.values.get("branch", "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", batch) or not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", branch):
            return render_template("dashB_admin.html", msg="Invalid batch or branch.")
        if batch and branch:
            ret = modelTrain.TrainImages(APP_ROOT, batch, branch)
            msg = ("Model Trained Successfully" if ret == 1 else "Training failed. Each student needs at least 5 clear, unique, single-face images.")
        else:
            msg = "Please provide batch and branch."
        return render_template("dashB_admin.html", msg=msg)
    return render_template("dashB_admin.html")

@bp.route("/admin/delete", methods=["POST", "GET"])
@role_required("Admin")
def deleteStudent():
    if request.method == "POST":
        entity = request.values.get("remove_id", "").strip()
        roll_id = request.values.get("id", "").strip()
        cursor = conn.cursor()
        if entity == "Student":
            cursor.execute(
                "SELECT 1 FROM attendance WHERE student_ID=%s LIMIT 1", (roll_id,)
            )
            if cursor.fetchone():
                return render_template(
                    "admin_remove.html",
                    msg="Cannot delete this student: historical attendance exists. Preserve the academic record.",
                )
            cursor.execute("DELETE FROM student_login WHERE BINARY roll_no=%s", [roll_id])
        elif entity == "Faculty":
            cursor.execute(
                "SELECT 1 FROM attendance WHERE faculty_ID=%s LIMIT 1", (roll_id,)
            )
            if cursor.fetchone():
                return render_template(
                    "admin_remove.html",
                    msg="Cannot delete this faculty account: historical attendance exists. Preserve the academic record.",
                )
            cursor.execute("DELETE FROM faculty_login WHERE BINARY faculty_id=%s", [roll_id])
        else:
            return render_template("admin_remove.html", msg="Invalid entity type.")

        conn.commit()
        msg = f"Successfully removed {roll_id}"
        return render_template("admin_remove.html", msg=msg)

    return render_template("admin_remove.html")

@bp.route("/admin/addRecord", methods=["POST", "GET"])
@role_required("Admin")
def addRecord():
    if request.method == "POST":
        entity = request.values.get("add_id", "").strip()
        username = request.values.get("username", "").strip().capitalize()
        password = request.values.get("password", "").strip()
        if not entity or not username or not password:
            return render_template("admin_add.html", msg="Please fill all fields.")
        if len(username) > 50:
            return render_template("admin_add.html", msg="Name must be 50 characters or fewer.")
        if entity == "Student" and not re.fullmatch(r"[A-Za-z0-9_-]{1,15}", password):
            return render_template("admin_add.html", msg="Student roll number must use 1–15 letters, digits, underscores or hyphens.")
        if entity == "Faculty" and not re.fullmatch(r"[A-Za-z0-9_-]{1,25}", password):
            return render_template("admin_add.html", msg="Faculty ID must use 1–25 letters, digits, underscores or hyphens.")
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
        except MySQLdb.IntegrityError:
            msg = "This record is already in the database"

        return render_template("admin_add.html", msg=msg)

    return render_template("admin_add.html")











# --------------------------- STUDENT REGISTRATION -------------------------- #


from services.file_storage import unzip_file

