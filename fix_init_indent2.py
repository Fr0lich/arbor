with open('ui/tutorial.py', 'r') as f:
    lines = f.readlines()

with open('ui/tutorial.py', 'w') as f:
    for line in lines:
        if line.startswith("                if target_widget:"):
            f.write("        if target_widget:\n")
        else:
            f.write(line)
