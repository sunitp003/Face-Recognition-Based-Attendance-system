# Face Recognition Based Attendance System

A Flask + MySQL attendance application using OpenCV Haar face detection and LBPH face recognition.

## Recognition pipeline

1. Each student uploads a ZIP containing clear, front-facing photos. Images are extracted to `uploads/<batch>/<branch>/<roll_no>/`.
2. Admin trains the model for the exact batch and branch.
3. Training accepts only images containing exactly one detectable face and requires at least three usable images per student.
4. The model is saved as `models/<batch>/<branch>/trainer.yml`; `labels.json` stores the exact student roll-number mapping. Keep these files together.
5. Faculty uploads a classroom video. Recognition samples frames and aggregates repeated LBPH predictions. A single frame is not enough to mark a student present.
6. Attendance is matched using exact roll-number equality. Partial/suffix ID matching is removed.

## Setup

Use Python 3.10 or 3.11 and MySQL 8.x.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create the database using `database_creation.sql` on a **new or backed-up database**. The legacy SQL file contains sample and cleanup statements; inspect it before running it against any database with real attendance data.

Set environment variables before starting the app:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Stable, random Flask session secret |
| `DB_HOST` | MySQL host (default 127.0.0.1) |
| `DB_PORT` | MySQL port (default 3306) |
| `DB_USER` | MySQL user (default root) |
| `DB_PASSWORD` | MySQL password |
| `DB_NAME` | Database name (default attendance_database1) |
| `LBPH_DISTANCE_THRESHOLD` | Maximum LBPH distance accepted (default 55; lower is stricter) |
| `LBPH_MIN_VOTES` | Minimum sampled-frame votes (default 3) |

Generate a persistent secret using `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never commit real credentials.

## Retrain after updating

The new training code uses a label-to-roll-number map. Retrain every batch/branch after deploying this update. Old `trainer.yml` files without a matching `labels.json` are rejected intentionally.

For each student, collect at least 10–20 varied photos where possible: front-facing and slight left/right turns, different natural lighting, neutral expression, no heavy filters, and one face per image. Avoid near-identical burst photos. Do not mix students in one student's folder.

## Accuracy and threshold calibration

LBPH is a classical appearance-based method, not a deep neural face embedding model. The default distance threshold is conservative but is not a universal accuracy guarantee. Calibrate it with separate validation videos from the actual camera, lighting, seating distance, and student population. Measure false accepts and false rejects separately. Lower the threshold to reduce wrong identities; raising it may increase false attendance.

Faculty should supervise attendance and review uncertain/no-match cases. Lighting, pose, occlusion, camera quality, and similar-looking faces affect recognition. This project does not implement liveness/anti-spoofing, so photo or replay attacks are not prevented.

## Operational notes

- Do not expose the Flask development server or database directly to the internet.
- Rotate any database password previously committed to source control.
- The legacy login schema stores passwords in plain text / uses roll numbers as student passwords. Replace it with per-user password hashes before production deployment.
- Keep uploaded datasets, videos, trained models, and database backups access-controlled; they contain sensitive biometric and attendance data.
