import re
with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# Fix indentation issue
content = content.replace("        def animate(self):", "    def animate(self):")
with open('ui/tutorial.py', 'w') as f:
    f.write(content)
