import re
with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# Fix indentation issue
content = content.replace("        def _cleanup(self):", "    def _cleanup(self):")
with open('ui/tutorial.py', 'w') as f:
    f.write(content)
