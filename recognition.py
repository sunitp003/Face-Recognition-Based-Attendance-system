"""Backward-compatible entry point for the face-recognition service.

Keep this module so existing imports, scripts and tests continue to work.
The implementation lives in services.face_recognition.
"""
from services import face_recognition as _implementation

globals().update({
    name: getattr(_implementation, name)
    for name in dir(_implementation)
    if not name.startswith("__")
})
