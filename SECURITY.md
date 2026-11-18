# Security and biometric-data operations

The application processes student names, roll numbers, attendance records, face photographs, derived face crops, trained LBPH models and temporary classroom media. Treat all of these as sensitive institutional data.

## Minimum operator controls

- Obtain informed institutional approval and student consent before collecting or processing biometric images.
- Restrict host and database access to authorized administrators; use a dedicated non-root MySQL account.
- Keep .env, database backups, uploads/, models/, detected_faces/ and attendance/ out of public web access and source control.
- Use HTTPS, secure session cookies, a strong stable SECRET_KEY, firewall rules and regular dependency/security updates.
- Back up the database and model/data directories before upgrades, retraining or cleanup.
- Define an institution-approved retention schedule for original photos, rejected-face crops, classroom videos, model files and backups. Delete data only under that approved schedule and verify backup expiry as well.
- Record who can view/export attendance and biometric data. Review faculty-wide visibility and least-privilege access before real deployment.

## Known limitations

- Haar Cascade + LBPH has no liveness or anti-spoofing protection. Printed photographs and replayed media may be accepted.
- Recognition thresholds are not calibrated for every camera, lighting condition or student population. Measure false accepts and false rejects with held-out local footage.
- Faculty confirmation remains mandatory. Never treat model suggestions as proof of attendance or absence.
- This repository does not implement a scheduled biometric retention/deletion job, encryption-at-rest for image/model directories, multi-factor authentication, or distributed login rate limiting. These must be addressed before institutional production use.
- CI tests do not replace integration testing against the college's real MySQL schema, camera hardware, video inputs and network environment.

Do not describe this system as certified, legally compliant, or production-approved without a separate institutional security, privacy and accuracy review.
