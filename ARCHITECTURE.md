# Architecture and regression safeguards

This refactor is intentionally additive and keeps the existing runtime contract.

## Preserved application contract

- Python, Flask, MySQL, OpenCV, Haar Cascade and LBPH remain the core stack.
- The database schema and existing attendance workflow are unchanged.
- Existing route paths, endpoint names, templates and form/session conventions remain in `app.py`.
- `modelTrain.py` and `recognition.py` remain compatibility entry points for older imports and scripts.
- Face recognition remains advisory: faculty review and confirmation are still required before attendance is written.

## Service boundaries

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

## Recognition constraints

No face algorithm, Haar Cascade configuration, LBPH configuration, recognition threshold, model format, database table or attendance approval rule is changed by this service extraction. Liveness detection and deep-learning embeddings are intentionally out of scope.
