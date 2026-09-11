with open('ui/tutorial.py', 'r') as f:
    lines = f.readlines()

with open('ui/tutorial.py', 'w') as f:
    for line in lines:
        if line.startswith("                        self.active_root = None"):
            f.write("            self.active_root = None\n")
        else:
            f.write(line)
