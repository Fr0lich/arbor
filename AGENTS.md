# Master AI Agent Guide for Arbor

Welcome, Agent. This file is your master router. Before you begin any task, you must determine what category your current task falls under and read the associated documentation *before* making any changes or proposing solutions.

---

## ⚠️ CRITICAL PROJECT STATUS & UI DIRECTION

* **Production Application is Tkinter (`ui/` + `main.py`)**: Arbor is an active, production desktop application written in **Tkinter**. All everyday features, bug fixes, enhancements, performance tuning, and database workflows belong in the Tkinter codebase (`ui/`).
* **PySide6 Migration is PAUSED at Phase 1**: The visual and structural extraction into PySide6 Qt Designer XML files (`.ui`) was **100% completed across all 32 files** and is preserved in `pyside_new_uis/`. Phase 2 (Python logic wiring) is **intentionally on hold** to keep Arbor simple, stable, zero-dependency, and immediately deployable without dual-stack maintenance overhead.
* **Never assume the app runs on PySide6**: Do NOT write new features in `ui_qt/` unless the user explicitly requests working on the experimental Qt blueprint.

### Folder Usage & Status Guide:
1. **`ui/` [ACTIVE PRODUCTION]**: The real, working UI. All production changes, dialogs, widgets, and layouts live here.
2. **`pyside_new_uis/` [COMPLETED PHASE 1 ASSET]**: Contains the 32 verified, 1:1 audited `.ui` files. Serves as a ready-to-wire blueprint if a future team ever decides to migrate to Qt. Verified via `python scripts/verify_all_uis.py`.
3. **`ui_qt/` [EXPERIMENTAL / OPTIONAL ARCHIVE]**: Early prototype Qt controllers from exploratory work. They point to the old `qt designer/` folder and do NOT wire up `pyside_new_uis/`. Treat as reference only.
4. **`qt designer/` [DEPRECATED / SUPERSEDED]**: Legacy, early `.ui` drafts. Completely superseded by `pyside_new_uis/`. Do not edit or use for new work.

---

## Task Routing Directory

* **Working on Tkinter UI, New Features, Layouts, or Bug Fixes? (DEFAULT)**
  * 👉 Read **`documentation/agent/codebase_guide.md`** and **`documentation/agent/feature_catalog.md`** for architecture.
  * 👉 Read **`documentation/agent/AI_UI_GUIDE.md`** for design system tokens (colors, padding, fonts).
  * 👉 Read **`documentation/agent/CLAUDE_BUG_REVIEW_GUIDE.md`** for performance, threading, and safe Pandas conventions.

* **Working on the Mobile Companion App or Backend Server (`mobile_server.py`)?**
  * 👉 Read **`documentation/agent/MOBILE_COMPANION_GUIDE.md`** (CRITICAL). This contains strict rules for frontend implementation, logic syncing, and performance.

* **Reviewing the PySide6 Blueprint or Resuming Qt Wiring?**
  * 👉 Read **`documentation/agent/PYSIDE6_MIGRATION_GUIDE.md`** (Status: Phase 1 complete, Phase 2 blueprint).
  * 👉 Read **`PYSIDE_UI_INTEGRATION_PIPELINE.md`** (Catalog of all 32 `.ui` files with exact widget object names and constructor contracts).
  * 👉 Run `python scripts/verify_all_uis.py` to validate XML schema compliance.

* **Working on Interactive Tutorials or User Onboarding?**
  * 👉 Read **`documentation/agent/TUTORIAL_GUIDE.md`** (CRITICAL). This contains strict rules for sandboxing, action-driven stepping, operational copy, and modular organization.

* **Looking for Past Code Reviews or Optimizations?**
  * 👉 Read **`documentation/agent/CODE_REVIEW.md`**.

## General Rules
- **Always route yourself** to the correct guide(s) based on your task prior to execution.
- If multiple guides apply, review all of them.
- Preserve working production code: Tkinter is the live engine.
