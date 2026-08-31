import re

with open("ui/widgets.py", "r", encoding="utf-8") as f:
    content = f.read()

# Instead of importing sc at the top where it might be causing circular imports or failing,
# we import it locally inside the classes or at the end of the file.
# The error `NameError: name 'sc' is not defined` means `sc` isn't accessible where it's used.

# Let's fix ArborDropdown and ArborTextField to import sc locally
def fix_sc(match):
    return "        from config import sc\n" + match.group(1)

content = re.sub(r"(        self\.rowconfigure\(0, weight=0\))", fix_sc, content)

with open("ui/widgets.py", "w", encoding="utf-8") as f:
    f.write(content)
