# College submission runbook (Windows)

Use a local MySQL 8 server and Python 3.10 or 3.11 (64-bit).

## 1. Prepare the project

Open PowerShell in the project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation for this terminal, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Edit .env and set SECRET_KEY to a long random value, plus your local MySQL username/password. The app loads .env automatically. Do not commit .env.

## 2. Create the database

Start MySQL, open MySQL Workbench or the MySQL command-line client as a database administrator, and execute database_creation.sql once on a new database. It creates tables and attendance triggers, but does not create a demo admin account.

Create a dedicated application account after the schema exists (replace the password):

```sql
CREATE USER 'attendance_app'@'localhost' IDENTIFIED BY 'REPLACE_WITH_A_STRONG_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE ON attendance_database1.* TO 'attendance_app'@'localhost';
FLUSH PRIVILEGES;
```

Set DB_HOST=127.0.0.1, DB_PORT=3306, DB_USER=attendance_app, DB_PASSWORD=your-password and DB_NAME=attendance_database1 in .env.

Generate an initial admin password hash (replace the example password locally):

```powershell
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('ChangeThisImmediately123!'))"
```

Copy the printed hash and insert it in MySQL:

```sql
INSERT INTO admin_login (username, password_hash) VALUES ('admin', 'PASTE_GENERATED_HASH_HERE');
```

Do not use the example password for a real deployment.

## 3. Start and verify

```powershell
python -m unittest discover -s tests -v
python app.py
```

Open http://127.0.0.1:5000 on the same laptop. Sign in as Admin, add student/faculty records, then sign in as a student and upload at least five distinct, clear face images in a ZIP. Train the matching batch/branch as Admin. Sign in as Faculty, process a short classroom video or photos, and manually verify every suggested student before saving attendance.

## 4. Demo safety

- Keep the app on the local laptop or trusted private network; do not expose Flask's development server to the public internet.
- Use consented sample faces only. Do not upload classmates' biometric photos without informed permission.
- Back up the database and uploads folder before changing or retraining datasets.
- The project has no liveness/anti-spoofing. A photo or replay can fool classical face recognition; faculty must verify results.
- If student registration rejects the ZIP, improve lighting/clarity and upload at least five unique images with exactly one detectable face per image.
- For actual production hosting, use Gunicorn behind HTTPS with a dedicated non-root DB account, private persistent storage, monitoring, backups and an approved biometric retention policy. This local demo setup is not production deployment.
