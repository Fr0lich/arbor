import re

with open('ui/tutorial.py', 'r') as f:
    content = f.read()

# Change except Exception: to except (Exception, tk.TclError): for position_popup
content = content.replace("except Exception:", "except (Exception, tk.TclError):")

with open('ui/tutorial.py', 'w') as f:
    f.write(content)
