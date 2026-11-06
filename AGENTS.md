# Master AI Agent Guide for Arbor

Welcome, Agent. This file is your master router. Before you begin any task, you must determine what category your current task falls under and read the associated documentation *before* making any changes or proposing solutions.

---

## ⚠️ CRITICAL PROJECT STATUS & UI DIRECTION

* **Production Application is Tkinter (`ui/` + `main.py`)**: Arbor is an active, production desktop application written in **Tkinter**. All everyday features, bug fixes, enhancements, performance tuning, and database workflows belong in the Tkinter codebase (`ui/`).
* **PySide6 Migration is PAUSED at Phase 1**: The visual and structural extraction into PySide6 Qt Designer XML files (`.ui`) was **100% completed across all 32 files** and is preserved in `pyside_new_uis/`. Phase 2 (Python logic wiring) is **intentionally on hold** to keep Arbor simple, stable, zero-friction, and immediately deployable without dual-stack maintenance overhead.
* **Never assume the app runs on PySide6**: Do NOT write new features in `ui_qt/` unless the user explicitly requests working on the experimental Qt blueprint.

### Folder Usage & Status Guide:
1. **`ui/` [ACTIVE PRODUCTION]**: The real, working UI. All production changes, dialogs, widgets, and layouts live here.
2. **`pyside_new_uis/` [COMPLETED PHASE 1 ASSET]**: Contains the 32 verified, 1:1 audited `.ui` files. Serves as a ready-to-wire blueprint if a future team ever decides to migrate to Qt. Verified via `python scripts/verify_all_uis.py`.
3. **`ui_qt/` [EXPERIMENTAL / OPTIONAL ARCHIVE]**: Early prototype Qt controllers from exploratory work. They point to the old `qt designer/` folder and do NOT wire up `pyside_new_uis/`. Treat as reference only.
4. **`qt designer/` [DEPRECATED / SUPERSEDED]**: Legacy, early `.ui` drafts. Completely superseded by `pyside_new_uis/`. Do not edit or use for new work.

---

## 📦 DEPENDENCY & DEPLOYMENT PHILOSOPHY: ZERO-FRICTION & OFFLINE-FIRST

Arbor follows a **Zero-Friction, Offline-First** architecture. When improving, maintaining, or adding features, all agents must adhere to the following principles:

1. **Zero User-Facing Installation Burden**:
   - The end user must **never** have to install external software, database engines, or background services (no PostgreSQL, MySQL, Redis, Docker, Node.js, npm, or system-level C++ compilers).
   - The desktop app must remain a double-clickable, portable application that freezes cleanly into a standalone Windows executable via **PyInstaller** (`build_exe.bat`).
2. **Strictly Offline-First**:
   - The core curation suite, database operations, and mobile companion auditing must work seamlessly in physical herbarium vaults with **zero internet or cellular connection**.
   - Cloud services (GBIF REST lookups, Pinggy/Cloudflare tunnels) are strictly optional enhancements with graceful offline fallbacks.
3. **Use Pre-Tested Pip Packages Over Handcrafted Fragile Code**:
   - Do **NOT** reinvent complex utilities from scratch when mature, well-tested Python packages exist. Standard, pre-compiled wheels installed via `pip` (tracked in `requirements.txt`) and bundled into PyInstaller are welcomed and encouraged.
4. **Mobile Companion Zero-Build Stack**:
   - The mobile companion frontend must remain strictly Vanilla HTML, JavaScript, and Tailwind CSS (via CDN script) embedded in `backend/mobile_server.py`. Never introduce Node.js, npm, or external build steps.

### Approved vs. Prohibited Library Checklist

| Category | Status | Examples / Scope |
| :--- | :--- | :--- |
| **Data & Excel Processing** | ✅ **Approved** | `pandas`, `openpyxl`, `python-calamine` |
| **Image & Museum Scans** | ✅ **Approved** | `pillow`, `tifffile`, `imagecodecs` |
| **Fuzzy Matching & String Parsing** | ✅ **Approved** | `rapidfuzz`, taxonomic parsers |
| **Caching & In-Memory State** | ✅ **Approved** | `cachetools` (LRU/TTL caches) |
| **Validation & Schema Safety** | ✅ **Approved** | `pydantic` (offline models) |
| **Logging & Diagnostics** | ✅ **Approved** | `loguru` |
| **External Database Daemons** | ❌ **PROHIBITED** | PostgreSQL, MySQL, MongoDB, Redis (use local Excel / SQLite / DuckDB) |
| **Container & Runtime Overhead** | ❌ **PROHIBITED** | Docker, Podman, system-level background services |
| **Node.js / Frontend Compilers** | ❌ **PROHIBITED** | npm, yarn, webpack, Vite, React, Vue (mobile frontend is pure Vanilla JS) |
| **OS-Level Mouse / Keystroke Hooking** | ❌ **PROHIBITED** | `pynput`, `pyautogui` (use native Tkinter event bindings) |

> ⚠️ **MANDATORY INSTRUCTION FOR AGENTS:**
> If a package you wish to suggest or introduce is **NOT explicitly listed on the Approved Checklist above**, you **MUST ASK THE USER FOR APPROVAL** and provide a clear technical justification (including its PyInstaller compatibility, offline viability, and bundle size impact) **before** adding it to `requirements.txt` or writing code that imports it.

---

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
