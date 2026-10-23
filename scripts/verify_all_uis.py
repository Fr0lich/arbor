import os
import subprocess
import sys

ui_dir = "pyside_new_uis"
files = sorted([f for f in os.listdir(ui_dir) if f.endswith(".ui")])
failed = []
passed = []

for f in files:
    path = os.path.join(ui_dir, f)
    res = subprocess.run([sys.executable, "scripts/verify_ui.py", path], capture_output=True, text=True)
    if res.returncode == 0 and "VERIFIED" in res.stdout:
        passed.append(f)
    else:
        failed.append((f, res.stderr or res.stdout))

print(f"Total .ui files: {len(files)}")
print(f"Passed: {len(passed)}")
print(f"Failed: {len(failed)}")
if failed:
    for name, err in failed:
        print(f"FAILED: {name} -> {err.strip()}")
else:
    print("ALL .ui FILES VERIFIED SUCCESSFULLY (EXIT CODE 0)!")
