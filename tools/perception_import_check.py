"""Simple smoke test for the isolated perception environment."""

from __future__ import annotations

import sys


def main() -> int:
    print(sys.executable)
    import cv2  # noqa: F401
    import chromadb  # noqa: F401
    import PIL  # noqa: F401
    import tensorflow  # noqa: F401
    import tf_keras  # noqa: F401
    from deepface import DeepFace  # noqa: F401
    from ultralytics import YOLO  # noqa: F401

    print("perception-imports-ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
