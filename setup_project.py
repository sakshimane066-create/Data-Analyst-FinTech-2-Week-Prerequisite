"""
setup_project.py
Creates the Day 1 folder structure + .gitignore.

Usage:  python setup_project.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FOLDERS = [
    "data/raw",
    "data/processed",
    "notebooks",
    "sql",
    "dashboard",
    "reports",
]

GITIGNORE = """# Python
venv/
.venv/
__pycache__/
*.pyc

# Jupyter
.ipynb_checkpoints/

# Misc
.env
.DS_Store
Thumbs.db
"""


def main() -> None:
    for folder in FOLDERS:
        path = ROOT / folder
        path.mkdir(parents=True, exist_ok=True)
        keep = path / ".gitkeep"  # lets Git track empty folders
        if not keep.exists():
            keep.touch()
        print(f"[ok] {folder}/")

    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE, encoding="utf-8")
        print("[ok] .gitignore")

    print("\nDone. Put your 10 provided CSV files in data/raw/")


if __name__ == "__main__":
    main()
