"""Safe upload extraction helpers."""
import logging
import os
import shutil
import uuid
import zipfile
from werkzeug.utils import secure_filename

def unzip_file(zip_src, dst_dir, roll_id, validator=None):
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
    image_entries = 0
    os.makedirs(staging, exist_ok=False)
    try:
        with zipfile.ZipFile(zip_src, "r") as archive:
            for item in archive.infolist():
                if item.is_dir():
                    continue
                filename = secure_filename(os.path.basename(item.filename))
                if not filename or not filename.lower().endswith(allowed):
                    continue
                image_entries += 1
                if image_entries > 30:
                    raise ValueError("ZIP may contain at most 30 JPG/JPEG/PNG images.")
                if item.file_size <= 0 or item.file_size > 8 * 1024 * 1024:
                    raise ValueError("Each image must be non-empty and no larger than 8 MB.")
                total_bytes += item.file_size
                if total_bytes > 40 * 1024 * 1024:
                    raise ValueError("The uncompressed image total must not exceed 40 MB.")
                destination = os.path.join(staging, f"{saved + 1}_{filename}")
                with archive.open(item) as source, open(destination, "wb") as target:
                    shutil.copyfileobj(source, target)
                saved += 1
        if not saved:
            return None
        # Validate staged images before replacing previously accepted samples.
        if validator is not None and not validator(staging):
            raise ValueError("At least five distinct, clear, single-face images are required.")
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
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        logging.warning("Student image ZIP rejected: %s", exc)
        return None
    finally:
        if os.path.exists(staging):
            shutil.rmtree(staging, ignore_errors=True)

