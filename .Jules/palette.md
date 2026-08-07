## 2024-05-18 - [Make ToggleSwitch Keyboard Accessible]
**Learning:** Custom Tkinter canvas-based widgets (like ToggleSwitch) are completely skipped by keyboard navigation (Tab key) by default. They require explicit focus management using `takefocus=1`, keyboard binding for `<space>`/`<Return>`, and `<FocusIn>`/`<FocusOut>` bindings for visible accessibility cues.
**Action:** Always check interactive canvas-based components for focus indicators and `takefocus` flags, and bind keyboard interactions directly to their click handlers to support screen readers and keyboard users.
