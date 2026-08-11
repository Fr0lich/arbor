import timeit

setup = """
class Root:
    def focus_get(self):
        return self.focus

class Window:
    def __init__(self, size, focus_idx):
        self.root = Root()
        self.location_entries = [object() for _ in range(size)]
        if focus_idx is not None:
            self.root.focus = self.location_entries[focus_idx]
        else:
            self.root.focus = object()

    def _get_focused_location_index_loop(self):
        current = self.root.focus_get()
        for i, w in enumerate(self.location_entries):
            if w == current:
                return i
        return None

    def _get_focused_location_index_index(self):
        current = self.root.focus_get()
        try:
            return self.location_entries.index(current)
        except ValueError:
            return None

win = Window(100, 50)
"""

print("Loop (match):", timeit.timeit("win._get_focused_location_index_loop()", setup=setup, number=100000))
print("Index (match):", timeit.timeit("win._get_focused_location_index_index()", setup=setup, number=100000))

setup_nomatch = setup.replace("Window(100, 50)", "Window(100, None)")
print("Loop (no match):", timeit.timeit("win._get_focused_location_index_loop()", setup=setup_nomatch, number=100000))
print("Index (no match):", timeit.timeit("win._get_focused_location_index_index()", setup=setup_nomatch, number=100000))
