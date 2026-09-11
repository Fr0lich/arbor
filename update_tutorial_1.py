import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# Add config import
if 'from config import sc' not in content:
    content = content.replace('import sys', 'import sys\nfrom config import sc\nimport config')

# Add COLORS definition
colors_code = """
COLORS = {
    "bg": "#ffffff",
    "surface": "#fbfaf8",
    "surface_dim": "#dadada",
    "border": "#c4c7c7",
    "primary": "#000000",
    "secondary": "#3a7d44",
    "text": "#2c302e",
    "text_muted": "#444748",
    "highlight": "#d9480f",
}

COLORS_DARK = {
    "bg": "#181c19",
    "surface": "#24273a",
    "surface_dim": "#1e2030",
    "border": "#363a4f",
    "primary": "#cad3f5",
    "secondary": "#8bd5ca",
    "text": "#cad3f5",
    "text_muted": "#a5adcb",
    "highlight": "#f5a97f",
}
"""

if 'COLORS =' not in content:
    content = content.replace('class TutorialManager:', colors_code + '\n\nclass TutorialManager:')

with open('ui/tutorial.py', 'w') as f:
    f.write(content)
