# Face Recognition Based Attendance System

A Flask + MySQL attendance application using **OpenCV Haar Cascade face detection** and **LBPH face recognition**. The existing Admin, Faculty and Student workflows are retained.

## Recognition and attendance workflow

1. Each student uploads a ZIP containing clear, front-facing photos. Images are extracted to `uploads/<batch>/<branch>/<roll_no>/`.
2. Admin trains the model for the exact batch and branch.
3. Training accepts only images containing exactly one detectable face, rejects blurry or badly lit images, removes exact duplicate face crops, requires at least five usable images per student, and caps each student's training set to 30 images.
4. The model is saved as `models/<batch>/<branch>/trainer.yml`; `labels.json` stores the exact model-label-to-roll-number mapping. Keep these files together.
5. Faculty uploads a classroom MP4. Recognition uses Haar Cascade + LBPH, rejects low-quality face crops and aggregates matches over separate one-second windows.
6. **Recognition suggestions are not saved automatically.** Faculty sees a review screen with model suggestions pre-selected, can correct the list, and must confirm before attendance is written to MySQL.
7. Attendance writes are performed in one database transaction. A failed write is rolled back instead of leaving partial attendance rows.

## Setup

Use Python 3.10 or 3.11 and MySQL 8.x.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Create the database using `database_creation.sql` on a **new or backed-up database**. The schema script is intended to create tables and triggers only; create an administrator account with your own credentials after setup. Never run destructive SQL against a database containing real attendance records.

Set environment variables before starting the app:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Stable, random Flask session secret |
| `DB_HOST` | MySQL host (default 127.0.0.1) |
| `DB_PORT` | MySQL port (default 3306) |
| `DB_USER` | MySQL user (default root) |
| `DB_PASSWORD` | MySQL password |
| `DB_NAME` | Database name (default attendance_database1) |
| `LBPH_DISTANCE_THRESHOLD` | Maximum LBPH distance accepted (default 42; lower is stricter) |
| `LBPH_MIN_VOTES` | Minimum distinct one-second evidence windows (default 5; minimum 3) |

Generate a persistent secret using `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never commit real credentials.

## Retrain after updating

Retrain every batch/branch after deploying the updated training code. Existing models should be backed up first. The model and its matching `labels.json` must be generated together.

For each student, collect at least 10–20 varied photos where possible: front-facing and slight left/right turns, different natural lighting, neutral expression, no heavy filters, and one face per image. Avoid near-identical burst photos. Do not mix students in one student's folder.

## Accuracy and threshold calibration

LBPH is a classical appearance-based method, not a deep neural face-embedding model. The default distance threshold and image-quality limits are conservative starting points, **not a universal accuracy guarantee**. Calibrate them using separate validation videos from the actual camera, lighting, seating distance and student population. Measure false accepts and false rejects separately. Lowering the distance threshold generally reduces false identities but may increase missed students.

Faculty must verify the complete suggested list before saving attendance. This human review is intentional: a false recognition must not automatically become a Present record, and an unrecognized student must not automatically become Absent without faculty review.

Lighting, pose, occlusion, camera quality and similar-looking faces affect recognition. The project does not implement liveness/anti-spoofing, so photo or replay attacks are not prevented.

## Operational and security notes

- Do not expose the Flask development server or database directly to the internet.
- Rotate any database password previously committed to source control.
- The legacy login schema stores passwords in plain text / uses roll numbers as student passwords. Replace it with per-user password hashes before production deployment.
- Keep uploaded datasets, videos, trained models and database backups access-controlled; they contain sensitive biometric and attendance data.


## Reliability and security hardening

The hardened branch adds the following safeguards:

- A request-scoped MySQL connection is opened only when a request needs the database and closed during Flask teardown. Do not share a connection between worker threads.
- Every POST form carries a session-bound CSRF token. Keep the session secret stable across restarts and all application workers.
- Production startup refuses to run without `SECRET_KEY`. Set `APP_ENV=production`, `SECRET_KEY` and `COOKIE_SECURE=1` behind HTTPS.
- Uploaded MP4 files are checked for an MP4 file-type marker and removed after recognition processing. Image ZIPs are extracted into a staging directory and replace old samples only after extraction succeeds.
- Pending faculty reviews are stored server-side rather than in the browser cookie and expire after two hours. All workers must share the same persistent application filesystem for this temporary storage.
- Excel downloads are generated in memory to avoid concurrent requests overwriting one shared filename.
- Admin deletion is blocked when a student or faculty member has historical attendance, preventing accidental cascade deletion of academic records.
- Training and recognition now measure brightness/blur before histogram equalization. Model and label files are paired with a SHA-256 manifest; incomplete or mismatched bundles are rejected.
- Recognition threshold parsing is validated and the default is deliberately stricter. Five separate one-second windows are required by default. These are conservative starting values, not a promise of accuracy.
- GitHub Actions compiles the project and runs unit regression tests.

### Important deployment steps after upgrading

1. Back up the MySQL database, student image datasets, and current models before deploying.
2. Set a persistent `SECRET_KEY` and database credentials through environment variables. Never use the Flask development server in production.
3. Retrain **every batch/branch** after deploying this version. A model must have a matching `manifest.json`; legacy models without a manifest are intentionally rejected until retrained.
4. Run the application over HTTPS and set `COOKIE_SECURE=1`.
5. Run the regression suite with `python -m unittest discover -s tests -v`.
6. Test using held-out classroom videos and manually compare false accepts, false rejects, and missed detections before real attendance use.

### Security limitation that still needs an account migration

The legacy account design still uses student roll numbers and faculty IDs as login credentials, and the original admin table stores plaintext passwords. This is not safe for production. Existing account records and the login UI need a coordinated password-reset/hash migration before public deployment. Do not expose this legacy login system to the internet.
