"""Short-lived, server-side attendance review state."""
import json
import logging
import os
import re
import secrets
import time
import uuid
from flask import session

PENDING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "instance", "pending_attendance"))

def _store_pending_attendance(data):
    os.makedirs(PENDING_DIR, exist_ok=True)
    token = uuid.uuid4().hex
    temporary_path = os.path.join(PENDING_DIR, token + ".tmp")
    final_path = os.path.join(PENDING_DIR, token + ".json")
    # Remove abandoned review files so interrupted sessions do not accumulate.
    now = time.time()
    for filename in os.listdir(PENDING_DIR):
        if not filename.endswith(".json"):
            continue
        stale_path = os.path.join(PENDING_DIR, filename)
        try:
            if now - os.path.getmtime(stale_path) > 7200:
                os.remove(stale_path)
        except OSError:
            logging.warning("Could not clean expired pending review: %s", stale_path)
    payload = dict(data)
    payload["created_at"] = now
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(payload, file)
    os.replace(temporary_path, final_path)
    session["pending_attendance_id"] = token

def _load_pending_attendance():
    token = session.get("pending_attendance_id", "")
    if not re.fullmatch(r"[a-f0-9]{32}", str(token)):
        return None
    path = os.path.join(PENDING_DIR, token + ".json")
    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        if time.time() - float(payload.get("created_at", 0)) > 7200:
            _clear_pending_attendance()
            return None
        return payload
    except (OSError, ValueError, TypeError):
        return None

def _clear_pending_attendance():
    token = session.pop("pending_attendance_id", None)
    if token and re.fullmatch(r"[a-f0-9]{32}", str(token)):
        try:
            os.remove(os.path.join(PENDING_DIR, token + ".json"))
        except FileNotFoundError:
            pass

