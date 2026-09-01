# Museum Object Visualizer (Arbor)

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)

Arbor is a Python-based desktop application designed to visualize, edit, and review museum object databases stored in Excel. It provides a robust interface for collections management, featuring offline mobile support, extensive undo/redo capabilities, and a highly customizable Tkinter-based UI.

> *[Placeholder: Screenshot of the main Desktop Application UI]*

---

## Table of Contents
1. [Features](#features)
2. [Prerequisites & Installation](#prerequisites--installation)
3. [Usage](#usage)
    - [Desktop Application](#desktop-application)
    - [Mobile Companion App](#mobile-companion-app)
4. [Testing](#testing)
5. [Project Architecture](#project-architecture)
6. [Configuration](#configuration)
7. [Troubleshooting & FAQ](#troubleshooting--faq)
8. [Contributing Guidelines](#contributing-guidelines)

---

## Features

- **Excel Integration:** Seamlessly import and export museum databases using standard Excel files.
- **Robust State Management:** Comprehensive Undo/Redo capabilities preventing data loss during editing.
- **Mobile Companion App:** An embedded Flask-based web app for mobile devices that supports offline data entry via IndexedDB, automatically syncing when connectivity is restored.
- **Custom Tkinter UI:** A highly ergonomic, dynamic, and responsive graphical user interface.
- **Event-Driven Architecture:** Decoupled UI updates and background threading using a lightweight EventBus system.
- **Data Integrity:** Strict sanitization against CSV/Excel Formula Injection (DDE) and timezone conflicts.

---

## Prerequisites & Installation

### Requirements
- Python 3.8 or higher.
- (Linux specific for UI testing) `sudo apt-get update && sudo apt-get install -y python3-tk xvfb`

### Installation
1. Clone the repository to your local machine.
2. Install the necessary Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## Usage

### Desktop Application
To launch the primary Arbor desktop client, simply run:
```bash
python main.py
```

### Mobile Companion App
The Mobile Companion App runs as a local background Flask service, allowing a mobile device on the same network (or via tunnel) to interact with the database.

> *[Placeholder: Screenshot of the Mobile Companion App interface]*

- **Starting the Server:** The desktop application dynamically assigns available ports and spawns the background daemon thread.
- **Tunneling:** You can expose this local server using tunnels like Pinggy. The desktop app manages authentication via an `X-Session-Token`.
- **Offline Mode:** The mobile companion uses a Service Worker and IndexedDB to cache the UI and store mutations locally when offline. Edits are flushed to the server once the connection is restored.

---

## Testing

Arbor utilizes `pytest` for its extensive test suite, ensuring UI, backend, and integration reliability.

### Running Tests (Linux / Headless Environments)
Since Arbor relies heavily on Tkinter, testing in a headless environment (like CI/CD pipelines) requires a virtual display.

1. Ensure required system packages are installed:
   ```bash
   sudo apt-get install -y python3-tk xvfb
   ```
2. Install testing specific dependencies if needed (e.g., `qrcode`, `pytest-xvfb`).
3. Run the test suite wrapped in `xvfb-run`:
   ```bash
   xvfb-run -a python3 -m pytest tests/
   ```

---

## Project Architecture

Arbor is structured to cleanly separate concerns between the UI, data repository, and background services:

- **UI Layer (`ui/`):** Built with Tkinter. Massive UI components are broken down logically and utilize `tk.Variable` traces for state syncing.
- **EventBus (`ui/state.py`):** Acts as the central Pub/Sub mechanism. Background threads (like the MobileServer or Task Queues) publish events (e.g., `DATABASE_UPDATED`), and the UI schedules thread-safe redraws using `self.root.after()`.
- **Backend Services (`backend/`):** Houses the `MobileServer`, background task queues, search, and filtering logic. The Mobile Server is an embedded Flask app.
- **Data Repository (`repository.py`):** Manages the core Pandas DataFrames (`df_reg`, `df_obs`), handling loading, saving, and data sanitization.

---

## Configuration

Arbor's settings and user preferences are managed via JSON and Python config files:

- **`config.py`:** Contains global application configuration definitions.
- **`arbor_preferences.json` / `user_prefs.json`:** Stores persistent user settings and window geometries.

---

## Troubleshooting & FAQ

**Q: The Mobile Server fails to start, complaining about "port already in use".**
A: This usually means a zombie process is still holding the port. You can find and kill it manually:
```bash
kill $(lsof -t -i :3000) 2>/dev/null || true
```
Arbor attempts to mitigate this by dynamically assigning available ports during startup.

**Q: I get a `TclError: no display name` when running tests.**
A: You are likely running Tkinter tests in a headless environment without an X server. Prefix your test command with `xvfb-run -a` (see the [Testing](#testing) section).

**Q: My mobile edits aren't saving!**
A: Check your connection status in the mobile app header. If offline, edits are queued in IndexedDB and will sync automatically when the connection is restored. Do not close the browser tab if you have pending offline edits.

---

## Contributing Guidelines

1. **Verify Your Work:** Always run the complete `pytest` suite before submitting changes.
2. **EventBus Over Direct Calls:** Never update the Tkinter UI directly from a background thread. Publish events to the global `app_bus` and let the UI subscribe to them.
3. **Widget Lifecycle:** Always use `.winfo_exists()` checks before querying widget geometry if `update_idletasks()` has been called, to prevent `bad window path name` exceptions.
4. **Mobile Frontend:** Do not create separate `.html` files for the mobile app. The single source of truth is the `INDEX_TEMPLATE` string within `backend/mobile_server.py`.

---

### Creating an Executable (.exe)
To build a standalone executable for Windows environments, simply run:
```batch
build_exe.bat
```
