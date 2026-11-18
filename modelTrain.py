"""Backward-compatible entry point for the face-training service.

Keep this module so existing imports, scripts and tests continue to work.
The implementation lives in services.model_training.
"""
from services import model_training as _implementation

globals().update({
    name: getattr(_implementation, name)
    for name in dir(_implementation)
    if not name.startswith("__")
})

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train attendance face model")
    parser.add_argument("root")
    parser.add_argument("batch")
    parser.add_argument("branch")
    args = parser.parse_args()
    raise SystemExit(0 if TrainImages(args.root, args.batch, args.branch) else 1)
