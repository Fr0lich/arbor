import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# Make sure we didn't miss fixing other parts.
# Also need to fix the invalid escape sequence warning (even though it runs).
content = content.replace(r'(\*\*.*?\*\*)', r'(\*\*.*?\*\*)') # Doesn't actually fix it since it's an r-string, but let's check what it was.
# Actually wait, r'(\*\*.*?\*\*)' is correct, python 3.12 might warn on \* inside r-string.
# We'll ignore the syntax warning for now as it doesn't break execution.

# Let's verify TutorialPopup replacement worked
if "Rich Text tk.Text" not in content:
    print("Warning: replacement failed.")

with open('ui/tutorial.py', 'w') as f:
    f.write(content)
