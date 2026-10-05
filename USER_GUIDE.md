# Arbor Botanical Database System — User Guide

Welcome to the **Arbor** user guide. Arbor is a desktop application designed for museum curators, botanists, and collection managers to visualize, edit, review, and validate botanical specimen datasets stored in Excel workbooks.

---

## Table of Contents
1. [User Interface & Workspace Layout](#1-user-interface--workspace-layout)
2. [Data Review & Problem Resolution Workflow](#2-data-review--problem-resolution-workflow)
3. [The Mobile Companion App](#3-the-mobile-companion-app)
4. [Searching & Data Filtering](#4-searching--data-filtering)
5. [ICEDIG & Missing Data Annotations](#5-icedig--missing-data-annotations)
6. [Keyboard Shortcuts Cheat Sheet](#6-keyboard-shortcuts-cheat-sheet)

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
* **Search Field:** Instantly search by ObjectID, Genus, or Species.
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

---

## 2. Data Review & Problem Resolution Workflow

### Identifying Problems
When a dataset is loaded, Arbor runs cross-validation checks against taxonomy registers and database rules. Problematic records are highlighted:
1. **Field-Level Flags:** Specific erroneous inputs are highlighted in red.
2. **Unmapped Badges:** Discrepancies that do not map directly to a single field appear as badges in the Problems section.

### Resolving Discrepancies (Historical & GBIF Conflict Resolver)
1. Navigate to a record showing the **History** indicator and click **History** (or press `Ctrl+H`).
2. The **Conflict Resolver** opens, showing side-by-side comparisons of:
   * Current Registration Value
   * Historical Ledger Entries
   * GBIF Backbone Taxonomy Suggestions
3. Click any suggested card to select it as the target resolution value.
4. Click **Apply Changes** (or press `Ctrl+A`) to commit the updates directly into the active record.

### Finalizing Verification
1. Once all mandatory fields and problems have been inspected and corrected, click **✓ MARK AS REVIEWED** at the bottom of the registration editor.
2. The record's `Reviewed` status becomes `True`, stamping your username and timestamp.
3. If **Auto-Advance** is enabled in Settings, Arbor automatically advances to the next unreviewed specimen.

---

## 3. The Mobile Companion App

Arbor includes a built-in Mobile Companion web application allowing physical herbarium sheet auditing using a smartphone or tablet.

### Setup & Connection
1. In Arbor, navigate to **Tools → Mobile Companion** (or click the Mobile icon on the toolbar).
2. Click **Start Server**. Arbor assigns a local port and displays:
   * A **QR Code** for instant mobile browser pairing.
   * A **Direct URL** (e.g. `http://192.168.1.50:5000/?pin=1234`).
   * An optional **Tunnel URL** (via Pinggy / Cloudflare) for secure remote access outside local Wi-Fi.
3. Scan the QR code with your mobile device to open the companion app.

### Offline Sync Architecture
* **IndexedDB Local Storage:** If Wi-Fi signal drops while working in the collection stacks, the mobile client continues functioning smoothly.
* **Offline Edits:** Changes and reviews are queued securely in the mobile browser's local IndexedDB.
* **Auto-Sync:** As soon as connectivity is re-established, pending edits are automatically dispatched to the desktop host and integrated safely via the Arbor EventBus.

---

## 4. Searching & Data Filtering

Arbor provides multi-dimensional filtering to quickly isolate records needing attention.

### Quick Search
* Press `Ctrl+F` to focus the search box.
* Type an ObjectID (e.g., `10423`) or partial taxon name (e.g., `Betula`).

### Advanced Filter Dialog (`Ctrl+G`)
Open the Filter Dialog by pressing `Ctrl+G` or choosing **View → Filter Objects**:
* **Review Status:** Filter by `Unreviewed Only`, `Reviewed Only`, or `All`.
* **Problem Category:** Isolate records with `Any Problem`, `Taxon Problems`, `Location Problems`, or specific flags.
* **Location & Collector:** Filter by Country, Collector Name, or Year range.
* **Preset Queries:** Save and load custom filter combinations for repetitive curation tasks.

---

## 5. ICEDIG & Missing Data Annotations

When transcribing historic labels where information is missing or obscured, use standard ICEDIG markers rather than leaving ambiguous blank spaces:

| Shortcut | Marker Value | Meaning |
| :--- | :--- | :--- |
| `Ctrl+Shift+M` or `?m` | `unknown:missing` | Information was omitted on the physical label. |
| `Ctrl+Shift+I` or `?i` | `unknown:indecipherable` | Text is physically illegible or damaged. |
| `Ctrl+Shift+U` or `?u` | `unknown:undigitized` | Information was skipped during initial digitization. |
| `Ctrl+Shift+W` or `?w` | `withheld` | Data is withheld due to conservation or legal sensitivity. |
| `Ctrl+Shift+Backspace` | `(Clear)` | Clears the field value completely. |

---

## 6. Keyboard Shortcuts Cheat Sheet

| Category | Shortcut | Action |
| :--- | :--- | :--- |
| **Navigation** | `Left` / `Right` | Move to Previous / Next specimen |
| | `Alt+Left` / `Alt+Right` | Navigate back / forward in browsing history |
| | `Enter` | Load typed ObjectID from search popup |
| **Focus & Panels** | `Ctrl+F` | Focus Search entry field |
| | `Ctrl+O` | Focus Object Listbox |
| | `Ctrl+E` / `Ctrl+I` | Focus first Registration metadata field |
| | `Ctrl+L` | Focus first Location field |
| | `Ctrl+P` | Focus first Problem checkbox |
| | `Ctrl+Q` | Toggle Focus Mode (minimalist layout) |
| | `F6` / `F7` / `F8` | Toggle Sidebar / Center Panel / Right Panel |
| **Editing** | `Ctrl+S` | Save session to Excel |
| | `Ctrl+Z` / `Ctrl+Y` | Undo / Redo last field change |
| | `Ctrl+R` / `Ctrl+Enter`| Toggle 'Reviewed' status |
| | `Ctrl+N` | Open New Object dialog |
| | `Ctrl+Shift+N` | Quick-create new specimen object |
| | `Ctrl+Shift+D` | Duplicate active specimen object |
| **Tools & History** | `Ctrl+H` | Open Historical & GBIF Conflict Resolver |
| | `Ctrl+G` | Open Filter Dialog |
| | `Ctrl+J` | View Database Statistics |
| **Image Viewport** | `Shift+Left` / `Shift+Right` | Previous / Next image in gallery |
| | `Mouse Wheel` | Zoom in / out |
| | `Click + Drag` | Pan high-resolution image |
