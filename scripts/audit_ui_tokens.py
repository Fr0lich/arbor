"""Audit all .ui files in qt designer/ against Arbor design tokens."""
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI_DIR = os.path.join(ROOT, "qt designer")

ALLOWED_COLORS = {
    "#fbfaf8": "SURFACE",
    "#ffffff": "CARD / WHITE",
    "#f2f5f1": "HEADER_ROW / LOW",
    "#e9ece5": "CONTAINER / HOVER",
    "#2c302e": "TEXT / PRIMARY HOVER",
    "#747878": "SUBTEXT / BORDER",
    "#c4c7c7": "HAIRLINE / DIVIDER",
    "#000000": "BLACK / PRIMARY BUTTON",
    "#3a7d44": "GREEN / SUCCESS / RECOMMENDED",
    "#c93a40": "RED / ERROR / REQUIRED",
    "#d9a036": "YELLOW / WARNING",
    "#4a7b9d": "BLUE / INFO",
    "#d95c14": "SEARCH_ORANGE",
}

# Documented Tkinter parity & specialized tokens:
SPECIAL_ALLOWED = {
    "#2d6a4f": "MOBILE GREEN (arbor.ui)",
    "#1b4332": "MOBILE GREEN HOVER (arbor.ui)",
    "#444748": "SUBTEXT / C_ON_VARIANT (Tkinter dialogs.py & PYSIDE6_MIGRATION_GUIDE)",
    "#2e6636": "GREEN HOVER (Darker hover for #3a7d44)",
    "#1a1a2e": "LOG VIEWER TERMINAL BG (Tkinter show_error_log_window)",
    "#e0e0e0": "LOG VIEWER TEXT (Tkinter show_error_log_window)",
}

ALLOWED_FONTS = {
    "'Segoe UI', 'Inter', -apple-system, sans-serif",
    "'Courier New', 'JetBrains Mono', monospace",
}

files = sorted(glob.glob(os.path.join(UI_DIR, "*.ui")))
print(f"Auditing {len(files)} .ui files in {UI_DIR}...\n")

issues_found = False

for f in files:
    fname = os.path.basename(f)
    with open(f, "r", encoding="utf-8") as fp:
        content = fp.read()

    # Find all stylesheets
    sheets = re.findall(r'<property name="styleSheet">\s*<string[^>]*>(.*?)</string>\s*</property>', content, re.DOTALL)
    
    font_issues = []
    color_issues = []
    radius_issues = []
    border_issues = []
    
    for s in sheets:
        for r in re.findall(r'border-radius:\s*([^;]+);', s, re.IGNORECASE):
            r_clean = r.strip()
            if r_clean not in ("0px", "2px"):
                radius_issues.append(r_clean)

        for b in re.findall(r'(?:^|;)\s*border(?:-(?:top|bottom|left|right|color|style|width))?:\s*([^;]+);', s, re.IGNORECASE):
            b_clean = b.strip().lower()
            if b_clean not in ("none", "0", "0px"):
                if not re.search(r'\b1px\b', b_clean):
                    border_issues.append(b_clean)

        for fm in re.findall(r'font-family:\s*([^;]+);', s, re.IGNORECASE):
            fm_clean = fm.strip()
            if fm_clean not in ALLOWED_FONTS:
                font_issues.append(fm_clean)

        for cm in re.findall(r'#[0-9a-fA-F]{3,8}\b', s):
            cm_l = cm.lower()
            if cm_l not in ALLOWED_COLORS and cm_l not in SPECIAL_ALLOWED:
                color_issues.append(cm)

    # Check font tags
    for fam in re.findall(r'<family>([^<]+)</family>', content):
        fam_clean = fam.strip()
        if fam_clean not in ("Segoe UI", "Inter", "Courier New", "JetBrains Mono"):
            font_issues.append(f"<family>{fam_clean}</family>")

    if font_issues or color_issues or radius_issues or border_issues:
        issues_found = True
        print(f"=== {fname} ===")
        if radius_issues:
            print(f"  Radius issues: {set(radius_issues)}")
        if border_issues:
            print(f"  Border issues: {set(border_issues)}")
        if font_issues:
            print(f"  Font issues: {set(font_issues)}")
        if color_issues:
            print(f"  Color issues: {set(color_issues)}")
        print()

if not issues_found:
    print("SUCCESS: All 19 .ui files strictly comply with Arbor design tokens and layout constraints!")
