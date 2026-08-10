import sys

def resolve_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()

    out_lines = []
    in_conflict = False
    in_ours = False
    in_theirs = False

    # We want to keep HEAD (ours) since this branch encapsulates the search/filter extraction

    for line in lines:
        if line.startswith('<<<<<<< HEAD'):
            in_conflict = True
            in_ours = True
            continue
        elif line.startswith('======='):
            in_ours = False
            in_theirs = True
            continue
        elif line.startswith('>>>>>>>'):
            in_conflict = False
            in_theirs = False
            continue

        if in_conflict:
            if in_ours:
                out_lines.append(line)
        else:
            out_lines.append(line)

    with open(filepath, 'w') as f:
        f.writelines(out_lines)

resolve_file('ui/database_ops.py')
resolve_file('ui/main_window.py')
