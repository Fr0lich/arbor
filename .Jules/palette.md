## 2024-05-19 - Added Hand Cursor to All Interactive Widgets

**Learning:** Native `tk` and `ttk` interactive widgets (`Button`, `Checkbutton`, `Radiobutton`, `Combobox`) do not automatically display a pointer (hand) cursor on hover like standard web interfaces or many other modern UI frameworks. This lack of micro-interaction feedback makes the desktop app feel clunky and unresponsive.

**Action:** Ensure `cursor="hand2"` is passed to all instances of clickable widgets across the codebase. Future PRs introducing new UI components in Tkinter must explicitly define this property to maintain standard desktop UX norms.
