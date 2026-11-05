# Arbor Project Archive

This folder stores preserved prototypes, design assets, and unreferenced modules that were archived during codebase cleanup:

1. **`ui/mobile_conflict_resolver.py`**:
   - Prototype modal UI (`MobileConflictResolverWindow`) for manual conflict resolution between desktop and mobile offline edits. Preserved in case this manual reconciliation UI is reintroduced into the mobile synchronization flow.
2. **`backend/mobile_scanner.py`**:
   - Prototype camera barcode/QR scanner HTML and JS snippets previously removed from `mobile_server.py`.
3. **`stitch designs/`**:
   - Static HTML and screenshot design mockups exported during the initial Stitch design system prototyping phase.
4. **`ui/advanced_search.py`**:
   - Standalone modal dialog (`AdvancedSearchDialog`) superseded by and merged into `ui/filter_dialog.py` ("Historical & Books" tab). Preserved for reference.
5. **`ui/advanced_settings.py`**:
   - Legacy advanced configuration dialog superseded by and unified into `ui/unified_settings.py` ("Advanced" and "Tools" tabs).
6. **`tests/test_advanced_settings.py`, `tests/test_tkinter_advanced_search.py`, `tests/test_repro.py`**:
   - Unit test suites written specifically against the retired standalone dialogs (`AdvancedSettingsWindow` and `AdvancedSearchDialog`). Preserved alongside their respective UI modules.
7. **`tests/test_qt_*.py` (Exploratory PySide6 Unit Tests)**:
   - Unit test suites (`test_qt_phase1.py` through `test_qt_phase7_polish.py`, `test_qt_filter_dialog.py`, `test_qt_remediation.py`, `test_qt_startup_dialog.py`, `test_qt_advanced_search.py`) written against the exploratory PySide6 prototype controllers in `ui_qt/`. Preserved here until Phase 2 Qt logic wiring is resumed.
