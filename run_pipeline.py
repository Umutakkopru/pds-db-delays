"""
Run the pipeline steps 01–05 in order (steps that do not exist yet are skipped).

Reads/writes: see the docstring of each step in src/
Usage: python run_pipeline.py
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STEPS = ["01_download.py", "02_clean.py", "03_enrich.py", "04_features.py", "05_train.py"]


def main() -> None:
    for step in STEPS:
        script = ROOT / "src" / step
        if not script.exists():
            print(f"--- {step}: not written yet, skipped")
            continue
        if step == "05_train.py":
            print("--- leakage tests")
            subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, check=True)
        print(f"--- {step}")
        subprocess.run([sys.executable, str(script)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
