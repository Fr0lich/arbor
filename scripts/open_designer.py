"""Helper script to launch Qt Designer for editing Arbor's .ui files.

Usage:
    python scripts/open_designer.py
    python scripts/open_designer.py "qt designer/filter_dialog.ui"
"""

import os
import sys
import subprocess
import PySide6


def main():
    designer_path = os.path.join(os.path.dirname(PySide6.__file__), "designer.exe")
    if not os.path.isfile(designer_path):
        print(f"Error: Qt Designer not found at: {designer_path}")
        sys.exit(1)

    args = [designer_path]
    if len(sys.argv) > 1:
        target_ui = sys.argv[1]
        if not os.path.isabs(target_ui):
            target_ui = os.path.abspath(target_ui)
        if not os.path.isfile(target_ui):
            print(f"Warning: File not found: {target_ui}")
        args.append(target_ui)

    print(f"Launching Qt Designer: {designer_path}")
    if len(args) > 1:
        print(f"Opening file: {args[1]}")

    subprocess.Popen(args)


if __name__ == "__main__":
    main()
