import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
result = subprocess.run(
    [sys.executable, os.path.join(BASE_DIR, "scripts", "qa_gate.py")],
    capture_output=True, text=True
)

for token in ("ERR_BBL_SYNTAX", "ERR_GFA_MISMATCH", "ERR_METER_INACTIVE", "ERR_PLUTO_MISSING"):
    assert token in result.stdout, f"Rule did not fire: {token}"

assert "CLEAN STAGING" in result.stdout
print("All gate rules fired as expected.")