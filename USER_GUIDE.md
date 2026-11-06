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
10. [Excel Workbook Structure & Data Specification](#10-excel-workbook-structure--data-specification)
11. [Application Updates & Version Management](#11-application-updates--version-management)

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
The Left Panel serves as the curator's control center, supporting dual viewing modes with instant responsiveness even across datasets with 20,000+ specimens:
* **Search Field:** Instantly search by ObjectID, Genus, or Species. Supports typo-tolerant fuzzy matching.
* **Dual View Modes (Compact vs. Detailed Cards):**
  * **Compact Mode (Treeview):** A dense 4-column tabular directory (`Status`, `ID`, `Genus`, `Species`) using standardized monospace glyphs (`✓` Reviewed, `!` Problem flag, `?` Historical ledger discrepancy, `•` Pending).
  * **Detailed Card Mode (Virtual Cards):** High-clarity virtual cards optimized for quick visual inspection. Each card features:
    * **Row 1:** Accession ID in bold monospace alongside the scientific taxon in italic serif, anchored by a **single high-contrast category badge** (`[ TAX ]`, `[ PROV ]`, `[ BOX ]`, `[ IMG ]`, `[ REV+ERR ]`, `[ REV ]`, `[ UNREV ]`).
    * **Row 2:** A clean, bullet-separated metadata line (`OBJ-0042 • PINACEAE • 2 photos • LOAN • UKN`) detailing family, attached photo counts, loan status, and unknown tags without visual clutter.
* **Curatorial Command Strip (Sticky Top Context Bar):**
  * **Accession Badge & Counter:** Monospace ID pill (`[ 10482 ]`) accompanied by real-time specimen count (`42 of 1,250`).
  * **Scientific Typography:** Botanical name displayed in *Lora* / *Georgia* italic serif with author citation in muted regular text.
  * **Interactive Status Pill:** Prominent, color-coded pill (`[ TAXONOMY ISSUE ]`, `[ PROVENANCE ERROR ]`, `[ ✓ REVIEWED ]`) that is directly clickable to launch the relevant problem resolver dialog.
  * **Unsaved Changes Indicator:** An amber `● Unsaved` dot dynamically appears next to the ID whenever edits are pending.
  * **Archival Action Buttons:** Quick-action buttons (`[ GBIF Verify ]`, `[ Books (N) ]`, `[ Send to Phone ]`) styled in quiet archival tones.
* **Smooth Sidebar Drawer:** The left panel smoothly expands and collapses via the Action Rail disclosure button (`◀` / `▶`) or `Ctrl+O`. Transitions use a 120ms cubic ease-out animation curve, preserving your custom dragged width between sessions.

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

* **FILE ▾**: Open Excel Workbooks (`Ctrl+O`), Save (`Ctrl+S`), Save As, Export Filtered Subset (CSV, Excel), Create Autosave Backup, and Exit.
* **SPECIMEN ▾**: Add New Specimen (`Ctrl+N`), Duplicate Record (`Ctrl+Shift+D`), Delete Active Record, Toggle Reviewed (`Ctrl+R`), and Auto-Advance options.
* **🌿 AUDIT & TOOLS ▾**: 
  * **Historical & GBIF Conflict Resolver (`Ctrl+H`)**: Reconcile specimen taxonomy against historical registries and GBIF.
  * **Specimen Problem Queue**: Step through flagged problem specimens in bulk.
  * **View Audit Log**: Inspect a complete timestamped changelog of all cell edits and session events.
  * **Database Statistics (`Ctrl+J`)**: Overview of collection completeness, taxonomy counts, and reviewer contributions.
  * **Filtered Subset Exporter**: Export active or filtered specimen datasets directly to local Excel (.xlsx) or CSV format.
* **VIEW ▾**: Toggle panels individually (`F6: Directory`, `F7: Registration`, `F8: Viewport`), toggle image rotation tools, and switch themes (`Dark Mode`).
* **📱 MOBILE**: Launch or stop the local Wi-Fi Companion Server, generate a QR code for mobile phone scanning, and sync photos taken on smartphones.
* **⚙ SETTINGS**: Access the Unified Settings dialog containing preferences for General, Appearance, Workspace Layout (including toggling the top bar navigation & problem jump cluster), Presets, Advanced Engine Flags, and the **Botanical Spelling Whitelist**.
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

Arbor includes a built-in mobile server allowing field assistants and curators to inspect physical specimen folders in herbarium vaults and collection stacks using any mobile smartphone or tablet:

* **Instant Zero-Config Pairing**: Click **📱 MOBILE** in the top navigation bar. Scan the on-screen QR code with your phone camera, or click **📋 Copy** to share the secure pairing link.
* **Campus & Eduroam Ready**: Choose **🌐 Public (Internet)** mode to automatically bypass institutional firewall client isolation via encrypted tunnels, or **📶 LAN only** for private offline travel routers.
* **100% Offline Vault Trust Engine**: When auditing deep in shielded collection stacks with zero Wi-Fi, all physical coordinate adjustments, review verification checkmarks, and notes are preserved locally in browser IndexedDB memory and auto-flushed to the workstation the moment Wi-Fi reconnects.
* **Rapid Physical Coordinate Steppers**: Easily increment or decrement Building, Floor, Cabinet, and Shelf numbers, tap values directly to open the mobile numeric keypad, or use **📋 Copy from Previous** to replicate coordinates across consecutive sheets in a folder.
* **Batch Location Registrator**: Move entire boxes or stacks of specimens to new cabinets in one continuous scanning workflow.
* **Standard Botanical ICEDIG Markers**: Built-in quick reference for standardized missing data markers (`unknown:missing`, `unknown:indecipherable`, `unknown:undigitized`, `withheld`) accessible directly in the mobile Settings modal.

*For complete step-by-step instructions, see the dedicated [Mobile Companion Field & Curator Guide](file:///c:/Users/ijbrekke/Documents/arbor/MOBILE_COMPANION_USER_GUIDE.md).*

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
| | `Up` / `Down` | Step through directory (instant context bar update, debounced media loading) |
| | `Ctrl+Up` / `Ctrl+Down` | Jump directly to Previous / Next specimen with active problems |
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

---

## 10. Excel Workbook Structure & Data Specification

Arbor uses standard Microsoft Excel workbooks (`.xlsx`) as its primary storage format, using Calamine and openpyxl for fast, non-destructive reading and writing. A fully curated Arbor workbook is organized into four sheets:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ARBOR WORKBOOK ARCHITECTURE                           │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│ 1. Registration │ 2. Observation  │ 3. Log          │ 4. Unvalidated_source │
│ (Catalog & Taxa)│ (Curation/Flags)│ (Audit Trail)   │ (Transcription Notes) │
│ • ObjectID (Key)│ • 11 Problems   │ • Timestamp ISO │ • ObjectID            │
│ • UID (GUID)    │ • Storage/Shelf │ • User & Action │ • Field_Name          │
│ • Taxonomy      │ • Reviewed state│ • Diffs & Log   │ • Unvalidated_Comment │
└─────────────────┴─────────────────┴─────────────────┴───────────────────────┘
```

### 1. The Minimum Viable Requirement ("The One Rule")
To open an existing spreadsheet in Arbor, your file only requires:
* A worksheet named **`Registration`** (case-insensitive, whitespace-tolerant).
* A primary key column named **`ObjectID`** (e.g. `1`, `1042`, `O-V-0042`).

All other sheets (`Observation`, `Log`, `Photo`, `Unvalidated_source`) are **optional**. When you save, Arbor automatically creates the companion sheets to store quality control flags and audit logs without modifying your original catalog columns.

### 2. Sheet Roles & Canonical Schema

#### A. `Registration` (The Specimen Catalog)
* **`ObjectID` (Primary Key):** Your catalog or accession number. Arbor normalizes this string, preserving leading zeros (`00142`), expanding scientific notation (`1.2E+04`), and stripping Excel `.0` float artifacts.
* **`UID` (System Fingerprint):** An 8-character hexadecimal identifier (e.g. `7921ac45`) automatically generated by Arbor to permanently track records across re-sorting or renaming.
* **Taxonomic Columns:** `Genus`, `Species`, `Author`, `Family`, `Higher Classification`.
* **Collection Event:** `Collector`, `Innsammling Nr.`, `Collection Date`, `Collection Place`.
* **Physical Specimen:** `Plant Part`, `Box Label`, `Conservation Status`.
* **Digital Media:** `Online photo 1`, `Online photo 2`, `Online photo 3` (or local image folder).

#### B. `Observation` (Quality Control & Storage Workspace)
* **Validation Problem Flags (11 Booleans):** Stored as strict booleans (`True` or `False`): `Genus_Problem`, `Species_Problem`, `Family_Problem`, `Author_Problem`, `PlantPart_Problem`, `Collector_Problem`, `Collection_Date_Problem`, `Collection_Place_Problem`, `Box_Label_Problem`, `Images_Problem`, `Other_problem`.
* **Physical Storage Hierarchy:** `Stored as` (e.g. *Mounted on wooden platform*, *Petridish*, *Box*), `Building` (*Lid's hus*), `Floor`, `Cabinet`, `Shelf`, `Loaned out`, `Loaned out date`.
* **Curation Verification:** `Reviewed` (`True`/`False`), `ReviewedAt` (ISO timestamp), `Images_Missing`, `Online_Images_Exist`.

#### C. `Log` (The Immutable Audit Trail)
* Automatically logs every curatorial modification to ensure museum audit and provenance compliance.
* Columns: `Timestamp` (ISO 8601), `Action` (`EDIT`, `REVIEW`, `DATABASE_CREATED`), `User`, `ObjectID`, `ChangedFields`, `ChangedValues` (*"OldValue" -> "NewValue"*), `ProblemsChanged`, `LocationChanged`, `SourceFile`, `OutputFile`.

#### D. `Unvalidated_source` (Transcription Notes & Scratchpad)
* A dedicated workspace for illegible handwriting, OCR drafts, or uncertain determinations.
* Columns: `ObjectID`, `Field_Name`, `Unvalidated_Comment` (e.g. *ObjectID: 1091 | Field: Species | Comment: box label says "sylvestris or similar"*).

### 3. Historical Accession Ledgers ("Books")
In the startup screen and under `SPECIMEN ▾ -> Load Historical Ledger Books...`, Arbor allows loading separate read-only Excel files representing transcribed 19th/20th-century physical museum accession ledgers.
* Arbor uses these ledger sheets in read-only mode to power the **Historical Conflict Resolver (`Ctrl+H`)**, cross-referencing modern catalog records against the original accession ledger to identify historical discrepancies.

### 4. Creating New Collections & The Demo Dataset
* **Create New Collection:** Click **+ Create New Database** in the startup dialog to open the **Collection Blueprint**. It gives an instant visual breakdown of the sheets, allows 1-click creation of a pre-formatted botanical workbook with sample records, or opens the 6-step `NewDatabaseWizard` for custom columns.
* **Explore Demo Project:** Click **🌿 Explore Demo Project** on the startup screen to load a lightweight 220-specimen slice (~11%) of real museum data with live online specimen photos, verified reviews, and real problem flags.

---

## 11. Application Updates & Version Management

Arbor includes a built-in, 1-click update system that queries GitHub Releases directly to keep your desktop curation environment up-to-date without external installers or third-party background services.

### Checking for Updates
You can check for updates at any time through three quick methods:
1. **Header Menu:** Click `❓ HELP ▾ -> 🔄 Check for Updates...`.
2. **Command Palette (`Ctrl+K`):** Type `update` and select `Check for Application Updates (GitHub)`.
3. **Settings Dialog:** Open `⚙ SETTINGS -> 🛠 Tools` and click `Check Now` under the **Application Updates & Version** card.

### The Seamless 1-Click Update Experience
When an update is found:
* **Release Notes & Verification:** The update modal displays the current version vs. newest version, alongside the formatted release notes from GitHub.
* **Non-Blocking Download:** Click **[ ⬇ Download & Install Update ]**. A progress bar streams the standalone executable directly into a safe staging directory (`.arbor_update/`).
* **Binary Integrity Guarantee:** Before any executable is accepted, Arbor inspects the DOS (`MZ`) and PE headers to ensure the download is a genuine Windows executable and not corrupted.
* **Curatorial Workflow Protection:**
  * When you click **[ 🔄 Restart & Restore Session ]**, Arbor flushes any in-flight input fields, triggers an emergency autosave, and captures your active workbook path and selected specimen ID into `~/.arbor/session_restore.json`.
  * If a Mobile Companion server or long-running GBIF batch is currently active, Arbor warns you and recommends **[ Apply on Next Exit ]** instead of an immediate restart.
* **Zero-Friction In-Place Swap:** Arbor performs an atomic NTFS swap (`arbor.exe` -> `arbor.old.{timestamp}.exe`) and instantly relaunches into the new binary with the `--restore-session` flag.
* **Instant Session Rehydration:** The newly launched Arbor version bypasses the startup screen, reopens your exact Excel catalog, jumps back to the specimen you were reviewing, and cleans up the temporary backup binaries automatically.

### Resilience Against Outages, Migrations & Renames
* **Repository Redirect Tracking:** If the GitHub repository is ever renamed or transferred (e.g., from `Fr0lich/arbor` to an organizational repository), Arbor follows HTTP 301/307 redirects automatically and silently persists the new URL in your user preferences.
* **Custom Repository Target:** If a network firewall, mirror, or internal fork is used, navigate to `⚙ SETTINGS -> 🛠 Tools -> Application Updates & Version`, enter the custom repository (e.g., `MyOrg/custom-arbor`), and click **Save Repo**. Click **Reset Default** at any time to return to the official upstream repository.
* **Offline-First & Graceful Fallback:** If internet access is unavailable or GitHub is experiencing an outage, Arbor notifies you non-blockingly without interrupting ongoing curation work. If installed in a read-only system folder (e.g. `Program Files`) without administrator privileges, Arbor gracefully directs you to the GitHub release page to download manually.
