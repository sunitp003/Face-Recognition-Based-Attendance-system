# Face Recognition Based Attendance System

A Flask + MySQL attendance application using OpenCV YuNet face detection and SFace deep face embeddings.

## Recognition pipeline

1. Student uploads a ZIP containing clear face photos. Images are extracted to `uploads/<batch>/<branch>/<roll_no>/`.
2. Admin downloads the OpenCV Zoo ONNX models once with `python download_models.py`.
3. Admin trains the batch/branch gallery. Enrollment accepts only images containing exactly one detectable face and requires at least three valid photos per student.
4. SFace creates normalized face embeddings, stored in `models/<batch>/<branch>/face_embeddings.json`. Student IDs are stored as exact roll-number strings; no partial or suffix matching is used.
5. Faculty uploads a classroom video. YuNet detects faces and SFace compares each embedding with the enrollment gallery using cosine similarity.
6. A match must pass both a similarity threshold and a best-vs-second-best margin, and must recur across multiple sampled frames before the student is marked Present.
7. If no confident identities are found, attendance is not written. The system does not silently mark the entire class Absent.

## Setup

Use Python 3.10 or 3.11 and MySQL 8.x.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Copy .env.example to .env and set your local MySQL credentials and a persistent SECRET_KEY.
# Windows: copy .env.example .env
# macOS/Linux: cp .env.example .env
python download_models.py
```

The model downloader retrieves YuNet and SFace ONNX weights from the official OpenCV model repositories. See the OpenCV Zoo examples for the detector/recognizer APIs: https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface and https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet.

Create the database using `database_creation.sql` on a **new or backed-up database**. The legacy SQL file contains sample and cleanup statements; inspect it before running it against any database with real attendance data.

Set environment variables before starting the app. See `.env.example`.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Stable, random Flask session secret |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | MySQL connection |
| `SFACE_COSINE_THRESHOLD` | Minimum cosine similarity (default 0.45; higher is stricter) |
| `SFACE_MIN_MARGIN` | Minimum gap over second-best identity (default 0.06) |
| `SFACE_MIN_VOTES` | Minimum sampled-frame confirmations (default 3) |

Generate a persistent secret using `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never commit real credentials.

## Retrain after updating

Retrain every batch/branch after deploying this update. The old LBPH trainer files are not used. The SFace gallery is rebuilt from each student's current upload folder.

For each student, use 10–20 varied photos where possible: front-facing and slight left/right turns, different natural lighting, neutral expression, no heavy filters, and one face per image. Avoid near-identical burst photos. Do not mix students in one student's folder.

## Accuracy and threshold calibration

SFace embeddings are generally more robust to pose and lighting variation than the old LBPH appearance classifier, but no threshold guarantees zero false matches. The defaults are intentionally conservative and may reject some genuine faces. Calibrate using separate held-out classroom videos from the actual camera, lighting, seating distance, and student population. Measure false accepts and false rejects separately. Raise the similarity threshold and/or margin to reduce false attendance; lowering them may increase false positives.

Faculty must supervise the generated attendance. Lighting, pose, occlusion, camera quality, very small faces, and similar-looking faces still affect results. This project does not implement liveness/anti-spoofing, so photo or replay attacks are not prevented.

## Operational notes

- Do not expose the Flask development server or database directly to the internet.
- Rotate any database password previously committed to source control.
- The legacy login schema stores passwords in plain text / uses roll numbers as student passwords. Replace it with per-user password hashes before production deployment.
- Keep uploaded datasets, videos, face embeddings, and database backups access-controlled; they contain sensitive biometric and attendance data.
