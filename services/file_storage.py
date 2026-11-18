"""Safe upload extraction helpers."""
import logging
import os
import shutil
import uuid
import zipfile
from werkzeug.utils import secure_filename

def unzip_file(zip_src, dst_dir, roll_id):
    """Extract a bounded image set, then atomically replace previous samples."""
    if not zipfile.is_zipfile(zip_src):
        return None
    os.makedirs(dst_dir, exist_ok=True)
    extract_to = os.path.join(dst_dir, str(roll_id))
    staging = os.path.join(dst_dir, f".{roll_id}.{uuid.uuid4().hex}.tmp")
    backup = os.path.join(dst_dir, f".{roll_id}.{uuid.uuid4().hex}.bak")
    allowed = (".jpg", ".jpeg", ".png")
    total_bytes = 0
    saved = 0
    os.makedirs(staging, exist_ok=False)
    try:
        with zipfile.ZipFile(zip_src, "r") as archive:
            for item in archive.infolist():
                if item.is_dir():
                    continue
                filename = secure_filename(os.path.basename(item.filename))
                if not filename or not filename.lower().endswith(allowed):
                    continue
                if item.file_size <= 0 or item.file_size > 8 * 1024 * 1024:
                    continue
                total_bytes += item.file_size
                if total_bytes > 40 * 1024 * 1024 or saved >= 200:
                    break
                destination = os.path.join(staging, f"{saved + 1}_{filename}")
                with archive.open(item) as source, open(destination, "wb") as target:
                    shutil.copyfileobj(source, target)
                saved += 1
        if not saved:
            return None
        if os.path.exists(extract_to):
            os.replace(extract_to, backup)
        try:
            os.replace(staging, extract_to)
        except OSError:
            if os.path.exists(backup):
                os.replace(backup, extract_to)
            raise
        if os.path.exists(backup):
            shutil.rmtree(backup, ignore_errors=True)
        return extract_to
    except (zipfile.BadZipFile, OSError, ValueError):
        logging.exception("Student image ZIP extraction failed")
        return None
    finally:
        if os.path.exists(staging):
            shutil.rmtree(staging, ignore_errors=True)

