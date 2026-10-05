"""Skeleton controller for the Qt main review workspace.

Phase 1 scope: load ``main_window_existing.ui`` and set the splitter
proportions. No data binding yet (forms, list, image viewer are Phase 1b).
"""
from ui_qt.loader import load_ui


class QtMainWindow:
    """Thin wrapper around the loaded .ui; will become the controller."""

    def __init__(self, app_state=None):
        self.app = app_state  # models.AppState (unused until data wiring)
        self.win = load_ui("main_window_existing.ui")
        # Mirror Tkinter pane weights: left 0 / center 3 / right 3
        self.win.splitter_main.setSizes([380, 640, 420])
        tree = self.win.tree_objects
        tree.setColumnWidth(0, 36)
        tree.setColumnWidth(1, 90)
        tree.setColumnWidth(2, 120)
        self.win.splitter_main.setStretchFactor(0, 0)
        self.win.splitter_main.setStretchFactor(1, 3)
        self.win.splitter_main.setStretchFactor(2, 3)
        self.win.splitter_left.setStretchFactor(0, 1)
        self.win.splitter_left.setStretchFactor(1, 0)

    def show(self):
        self.win.show()
