# Architecture and regression safeguards

This refactor is intentionally additive and keeps the existing runtime contract.

## Preserved application contract

- Python, Flask, MySQL, OpenCV, Haar Cascade and LBPH remain the core stack.
- The database schema and existing attendance workflow are unchanged.
- Existing route paths, endpoint names, templates and form/session conventions remain in `app.py`.
- `modelTrain.py` and `recognition.py` remain compatibility entry points for older imports and scripts.
- Face recognition remains advisory: faculty review and confirmation are still required before attendance is written.

## Service boundaries

The Flask application is created by `create_app()` and registers five blueprints: Authentication (`auth`), Admin (`admin`), Student (`student`), Faculty (`faculty`) and general pages (`pages`). Legacy endpoint aliases are registered so existing `url_for()` calls and external integrations continue to resolve.


| Module | Responsibility |
| --- | --- |
| `services/model_training.py` | Existing Haar Cascade/LBPH training implementation |
| `services/face_recognition.py` | Existing model verification, video sampling, LBPH recognition and vote aggregation |
| `services/file_storage.py` | Bounded ZIP extraction and atomic replacement of student image samples |
| `services/pending_attendance.py` | Short-lived server-side attendance review state |
| `services/security.py` | Session role guard and CSRF request protection |
| `database.py` | Request/application-context scoped MySQL connection lifecycle |
| `app.py` | Existing Flask routes, templates and orchestration |

## Compatibility

The root-level training and recognition modules re-export the service implementations, including helper symbols used by existing tests and scripts. This allows callers to migrate gradually without changing the existing import paths.

## Validation

Run locally from the repository root:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
```

GitHub Actions runs the same compile and regression checks for pushes to `main` and `refactor/**`, and for pull requests targeting `main`.

## Attendance input modes

Faculty can choose one of three sources on the attendance screen:

- **Photos:** upload up to 30 JPG/JPEG/PNG classroom photos in one submission. Each photo contributes at most one candidate vote per student; this helps cover a large class across multiple angles.
- **Video:** upload one MP4 recording. Existing frame sampling and multi-window vote aggregation are used.
- **College CCTV:** when the server is configured with `CCTV_RTSP_URL`, faculty can run a bounded live capture. `CCTV_CAPTURE_SECONDS` defaults to 300 seconds and is clamped to 30–900 seconds. The RTSP URL is configured only on the server and is never accepted from a browser form. OpenCV RTSP open/read timeouts are bounded.

For CCTV, the Flask server must run on a machine that can reach the camera/NVR over the college LAN or VPN. Configure the stream URL and credentials as deployment secrets/environment variables, not in Git. Use a dedicated read-only camera account. Camera use must be authorized by the institution and follow its student notice, consent, retention and privacy policies. This flow processes a bounded stream and then opens the same faculty review screen; it is not a continuous unattended attendance service.

All three modes produce suggestions only. Faculty review and confirmation remain mandatory before database writes. The upload request is limited to 50 MB total; photo mode allows up to 30 images.

## Recognition constraints

No face algorithm, Haar Cascade configuration, LBPH configuration, recognition threshold, model format, database table or attendance approval rule is changed by this service extraction. Liveness detection and deep-learning embeddings are intentionally out of scope.
