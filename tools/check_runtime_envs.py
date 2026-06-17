from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "tools" / "runtime_env.conf"


def read_runtime_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def report_env(name: str, venv_name: str, python_spec: str) -> list[str]:
    venv_path = REPO_ROOT / venv_name
    python_path = venv_path / "Scripts" / "python.exe"
    activate_path = venv_path / "Scripts" / "activate.bat"
    return [
        f"{name}:",
        f"  venv name: {venv_name}",
        f"  python spec: {python_spec}",
        f"  venv exists: {'yes' if venv_path.exists() else 'no'}",
        f"  python exists: {'yes' if python_path.exists() else 'no'}",
        f"  activate script exists: {'yes' if activate_path.exists() else 'no'}",
    ]


def main() -> int:
    if not CONFIG_PATH.exists():
        print(f"Missing config file: {CONFIG_PATH}")
        return 1

    config = read_runtime_config(CONFIG_PATH)
    print(f"Runtime config: {CONFIG_PATH}")
    print()

    required_keys = [
        "PERCEPTION_VENV",
        "PERCEPTION_PYTHON_SPEC",
        "DEEPFACE_VENV",
        "DEEPFACE_PYTHON_SPEC",
    ]
    missing = [key for key in required_keys if key not in config]
    if missing:
        print("Missing keys:")
        for key in missing:
            print(f"  - {key}")
        return 1

    for line in report_env(
        "Perception",
        config["PERCEPTION_VENV"],
        config["PERCEPTION_PYTHON_SPEC"],
    ):
        print(line)
    print()
    for line in report_env(
        "DeepFace",
        config["DEEPFACE_VENV"],
        config["DEEPFACE_PYTHON_SPEC"],
    ):
        print(line)

    print()
    print(f"Current interpreter: {sys.executable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
