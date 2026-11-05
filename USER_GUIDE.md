# Arbor Botanical Database System — User Guide

Welcome to the **Arbor** user guide. Arbor is a desktop application designed for museum curators, botanists, and collection managers to visualize, edit, review, and validate botanical specimen datasets stored in Excel workbooks.

---

## Table of Contents
1. [User Interface & Workspace Layout](#1-user-interface--workspace-layout)
2. [Top Navigation Bar & Dropdown Menus](#2-top-navigation-bar--dropdown-menus)
3. [Universal Command Palette (Ctrl+K) & Quick Switcher](#3-universal-command-palette-ctrlk--quick-switcher)
4. [Data Review & Problem Resolution Workflow](#4-data-review--problem-resolution-workflow)
5. [The Mobile Companion App](#5-the-mobile-companion-app)
6. [Searching & Data Filtering](#6-searching--data-filtering)
7. [Interactive Walkthrough Tutorials & Help Center](#7-interactive-walkthrough-tutorials--help-center)
8. [ICEDIG & Missing Data Annotations](#8-icedig--missing-data-annotations)
9. [Keyboard Shortcuts Cheat Sheet](#9-keyboard-shortcuts-cheat-sheet)

---

## 1. User Interface & Workspace Layout

Arbor's main workspace is organized into three primary vertical panels designed for ergonomic, high-throughput specimen curation:

```
┌─────────────────┬───────────────────────────────┬───────────────────────────────┐
│  1. OBJECT LIST │       2. IMAGE VIEWPORT       │     3. REGISTRATION PANEL     │
│                 │                               │                               │
│ [Search & Filter│  High-resolution specimen     │  • Genus / Species / Taxon    │
│  ObjectID list  │  images with zoom/pan/rotate  │  • Locality & Coordinates     │
│  Status badges] │  Local & remote gallery       │  • Problem Flags & Resolution │
│                 │                               │  • [✓ Mark as Reviewed]       │
└─────────────────┴───────────────────────────────┴───────────────────────────────┘
```

### Left Panel: Object Directory & Navigation
* **Search Field:** Instantly search by ObjectID, Genus, or Species. Supports typo-tolerant fuzzy matching.
* **Specimen List:** Displays all records in the active database or filtered subset. 
* **Indicators:** 
  * 🔴 **Red dot / highlight:** Specimen has unresolved problem flags.
  * 🟢 **Green checkmark:** Specimen has been marked as reviewed.
  * 🟡 **Yellow indicator:** Specimen has historical or taxonomic discrepancies available in reference databases.

### Middle Panel: Image Viewport & Location Data
* **High-Resolution Specimen Images:** View attached scans, photos, or remote image URLs.
* **Navigation & Zoom Toolbar:** Use the floating toolbar or mouse wheel to zoom (`Scroll`), pan (`Click + Drag`), and rotate (`90° CW/CCW`).
* **Location Center Mode (Optional):** Can display geographical locality, coordinates (latitude/longitude), and elevation right underneath or next to the image viewport for quick label transcription.

### Right Panel: Registration Editor & Problem Flags
* **Taxonomic & Specimen Metadata:** Edit fields such as `Taxon`, `Author`, `Collector`, `CollectorNumber`, `Day`, `Month`, `Year`, `Locality`, `Country`, and `Notes`.
* **Problem Flag Checkboxes:** Flag or clear validation errors (e.g., `Taxon_Mismatch`, `Coordinate_Problem`, `Unidentified`, `Missing_Data`).
* **Historical Conflict Trigger:** Click the **History** indicator button (or press `Ctrl+H`) to open the Historical & GBIF Conflict Resolver.
* **Review Verification:** Click **✓ MARK AS REVIEWED** (or press `Ctrl+Enter` / `Ctrl+R`) to timestamp and sign off on the record.

### Bottom Strip: Status & Telemetry Bar
The bottom bar provides a non-intrusive, real-time telemetry readout:
* **Active File:** File path or name of the currently opened workbook.
* **Selection & Count:** Active specimen index and total count (e.g. `Record 42 of 1,250 (Filtered: 140)`).
* **Curation Progress Bar:** Visual progress meter indicating percentage of dataset marked as reviewed.
* **Autosave Status:** Timestamp of the last background backup or auto-save.

---

## 2. Top Navigation Bar & Dropdown Menus

All primary operations in Arbor are logically grouped across seven clean header menus:

* **FILE ▾**: Open Excel Workbooks (`Ctrl+O`), Save (`Ctrl+S`), Save As, Export (Darwin Core, CSV, Excel), Create Autosave Backup, and Exit.
* **SPECIMEN ▾**: Add New Specimen (`Ctrl+N`), Duplicate Record (`Ctrl+Shift+D`), Delete Active Record, Toggle Reviewed (`Ctrl+R`), and Auto-Advance options.
* **🌿 AUDIT & TOOLS ▾**: 
  * **Historical & GBIF Conflict Resolver (`Ctrl+H`)**: Reconcile specimen taxonomy against historical registries and GBIF.
  * **Specimen Problem Queue**: Step through flagged problem specimens in bulk.
  * **View Audit Log**: Inspect a complete timestamped changelog of all cell edits and session events.
  * **Database Statistics (`Ctrl+J`)**: Overview of collection completeness, taxonomy counts, and reviewer contributions.
  * **Darwin Core Exporter**: Export occurrence packages meeting international DwC standards.
* **VIEW ▾**: Toggle panels individually (`F6: Directory`, `F7: Viewport`, `F8: Registration`), toggle image rotation tools, and switch themes (`Dark Mode`).
* **📱 MOBILE**: Launch or stop the local Wi-Fi Companion Server, generate a QR code for mobile phone scanning, and sync photos taken on smartphones.
* **⚙ SETTINGS**: Access the Unified Settings dialog containing preferences for General, Appearance, Workspace Layout, Presets, Advanced Engine Flags, and the **Botanical Spelling Whitelist**.
* **❓ HELP ▾**: Launch step-by-step interactive onboarding tutorials, open this User Guide, view the Keyboard Shortcuts cheat sheet (`F1`), and display About Arbor.

---

## 3. Universal Command Palette (Ctrl+K) & Quick Switcher

Pressing **`Ctrl+K`** (or `Ctrl+Shift+K`) anywhere in Arbor opens the **Universal Command Palette**:
* **Fuzzy Command Search:** Type any keyword (e.g. `save`, `export`, `dark`, `gbif`, `stats`, `mobile`) to instantly find and execute commands without searching through menus.
* **Direct Specimen Accession Jump:** Prefix your search with `#` or numbers (e.g. `#1042` or `1042`) to jump straight to that specimen accession record.
* **Keyboard Driven:** Use `Up` / `Down` arrows to navigate results and press `Enter` to execute immediately.

---

## 4. Data Review & Problem Resolution Workflow

### Identifying Problems
When a dataset is loaded, Arbor runs cross-validation checks against taxonomy registers and database rules. Problematic records are highlighted:
1. **Field-Level Flags:** Specific erroneous inputs are highlighted in red.
2. **Unmapped Badges:** Discrepancies that do not map directly to a single field appear as badges in the Problems section.

### Resolving Discrepancies (Historical & GBIF Conflict Resolver)
1. Press `Ctrl+H` or click the **History** indicator button on any specimen.
2. The conflict window displays parallel columns: **Current Registry Data**, **Historical Archive Match**, and **GBIF Taxonomic Backbone Match**.
3. Click any suggested cell or **Accept Suggestion** to adopt validated taxonomy with one click.
4. Accepted changes are immediately recorded in the audit changelog.

---

## 5. The Mobile Companion App

Arbor includes a built-in mobile server allowing field assistants and curators to edit records and capture photos on mobile phones via local Wi-Fi without cloud dependencies:
1. Click **📱 MOBILE** in the top navigation bar.
2. Click **Start Mobile Server**.
3. Scan the displayed QR code with your smartphone camera to open the mobile interface.
4. Photos taken on the phone are automatically paired with the active desktop specimen and saved to the configured image folder.

---

## 6. Searching & Data Filtering

* **Instant Search:** Press `Ctrl+F` to jump to the search box. Uses typo-tolerant fuzzy matching for genus, species, and collector names.
* **Advanced Multi-Criteria Filtering:** Press `Ctrl+G` to open the Filter Dialog:
  * Filter by Review Status (`Reviewed`, `Unreviewed`).
  * Filter by Problem Status (`Any Problem`, `Taxon Problem`, `Location Problem`).
  * Filter by Image Availability (`Has Images`, `Missing Images`).
  * Historical & Books cross-querying.

---

## 7. Interactive Walkthrough Tutorials & Help Center

Arbor includes built-in, sandboxed interactive tutorials designed to onboard new curators quickly without risking real data:
* **Accessing Tutorials**:
  * Open the **`HELP ▾`** menu and hover over **`🎓 Interactive Walkthrough Tutorials`**, or press **`Ctrl+K`** and type `tutorial`.
  * Open the central **`🏛️ Help Center...`** from the Help menu to view all learning guides and cheat sheets in one place.
* **Available Walkthroughs**:
  1. **Specimen Review & Verification**: Learn how to navigate the object tree, inspect specimen photos, check field values, and mark records as reviewed (`Ctrl+Enter`).
  2. **Historical & GBIF Conflict Resolution**: Learn how to identify discrepancies between your active dataset, historical ledger books, and online GBIF taxonomy, and resolve differences field by field.
  3. **Database Creation & New Accessions**: Learn how to use the Database Setup Wizard, configure schema fields, and quickly accession new specimens (`Ctrl+Shift+N`).
* **Sandbox Safety**: All tutorials run inside an isolated, in-memory sandbox (`SandboxManager`). Your active workbook is automatically snapshot on entry and restored when you finish or exit.

---

## 8. ICEDIG & Missing Data Annotations

When transcribing historic labels where information is missing or obscured, use standard ICEDIG markers rather than leaving ambiguous blank spaces:

| Shortcut | Marker Value | Meaning |
| :--- | :--- | :--- |
| `Ctrl+Shift+M` or `?m` | `unknown:missing` | Information was omitted on the physical label. |
| `Ctrl+Shift+I` or `?i` | `unknown:indecipherable` | Text is physically illegible or damaged. |
| `Ctrl+Shift+U` or `?u` | `unknown:undigitized` | Information was skipped during initial digitization. |
| `Ctrl+Shift+W` or `?w` | `withheld` | Data is withheld due to conservation or legal sensitivity. |
| `Ctrl+Shift+Backspace` | `(Clear)` | Clears the field value completely. |

---

## 9. Keyboard Shortcuts Cheat Sheet

| Category | Shortcut | Action |
| :--- | :--- | :--- |
| **Omni-Search & Palette** | `Ctrl+K` | Open Universal Command Palette & Specimen Switcher |
| | `Ctrl+F` | Focus Instant Search Bar |
| | `Ctrl+G` | Open Multi-Criteria Filter Dialog |
| | `Ctrl+Shift+F` | Open Filter Dialog on Historical & Books Search Tab |
| **Navigation** | `Left` / `Right` | Move to Previous / Next specimen |
| | `Alt+Left` / `Alt+Right` | Navigate back / forward in browsing history |
| **Workspace & Panels** | `F6` | Toggle Left Directory (Object List) |
| | `F7` | Toggle Right Registration & Taxonomy Panel |
| | `F8` | Toggle Middle Image Viewport |
| | `Ctrl+O` | Expand / Collapse Left Sidebar Drawer |
| | `Ctrl+P` | Quick Peek Specimen Inspector |
| | `Ctrl+Q` | Toggle Focus Mode (hide non-problem fields) |
| | `Ctrl+E` / `Ctrl+I` | Focus first Registration metadata field |
| | `Ctrl+L` / `F4` | Focus first Location field |
| | `Ctrl+Shift+P` / `F3` | Focus first Problem checkbox |
| | `Ctrl+PageUp` / `Ctrl+PageDown` | Cycle taxonomy sub-tabs |
| **Editing & Review** | `Ctrl+S` | Save session manually |
| | `Ctrl+Z` / `Ctrl+Y` | Undo / Redo last field change |
| | `Ctrl+R` / `Ctrl+Enter`| Mark active specimen as Reviewed |
| | `Space` | Toggle focused Problem checkbox |
| | `Ctrl+N` | Open New Specimen Wizard |
| | `Ctrl+Shift+N` | Quick Create next sequential accession |
| | `Ctrl+Shift+D` | Duplicate active specimen record |
| | `Ctrl+Delete` | Delete active specimen record |
| | `Ctrl+Shift+C` / `Ctrl+Shift+V` | Copy / Paste active field value |
| **Audit & Tools** | `Ctrl+H` | Open Historical & GBIF Conflict Resolver |
| | `Ctrl+J` | Open Database Statistics Dashboard |
| | `Ctrl+Alt+K` | Apply default data preset |
| | `F1` | Open Keyboard Shortcuts HUD Dialog |
| **Image Viewport** | `Alt+R` | Rotate specimen image 90° clockwise |
| | `Ctrl+Plus` / `Ctrl+Minus` | Zoom image in / out |
| | `Ctrl+0` | Reset image zoom and pan position |
| | `Shift+Left` / `Shift+Right` | Previous / Next image in attached gallery |
| | `Mouse Wheel` | Zoom in / out on image canvas |
| | `Click + Drag` | Pan high-resolution image |
| | `Double-click` | Open current image in external web browser |
