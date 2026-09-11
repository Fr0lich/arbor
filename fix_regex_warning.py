import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# Fix the invalid escape sequence warning
content = content.replace(r"r'(\*[^\*]+\*)'", r"r'(\*[^*]+\*)'")

with open('ui/tutorial.py', 'w') as f:
    f.write(content)
