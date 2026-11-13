# Arbor Master Documentation Architecture & Trainee Curriculum Map

**Version**: 1.0.0 (Production Foundation)  
**Target Audience**: Inexperienced trainees, work-placement interns, collection volunteers, and museum assistants  
**Core Design Philosophy**: Zero-Jargon, Action-Driven Progressive Disclosure, 100% Offline-First  
**Author**: Lead Documentation Architect & User-Assistance Specialist  

---

## 🧭 Executive Summary & Pedagogical Framework

Arbor is an offline-first desktop museum collection suite engineered for physical herbarium curation, digitizing accession sheets, checking plant labels, and auditing storage boxes.

The user profile for Arbor's daily operations is **distinct from general enterprise software**:
* **Minimal computer comfort**: Many trainees have never edited a database, used a command line, or configured an application beyond clicking buttons.
* **Zero botanical background**: Interns may not know botanical Latin, taxonomic rank hierarchies, or nomenclatural codes; they are transcribing physical text written on 19th- and 20th-century paper sheets.
* **High volume, physical task**: Curators sit at a physical desk with physical specimens, a barcode wand, and a keyboard. Glanceability and muscle memory trump lengthy explanations.

### The 4-Tier Progressive Disclosure Curriculum

To prevent cognitive overload, Arbor's user assistance is divided into four strictly demarcated learning tiers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   ARBOR 4-TIER PROGRESSIVE DISCLOSURE                       │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│ Tier 1 (10 Min) │ Tier 2 (At Desk)│ Tier 3 (Stuck)  │ Tier 4 (Task-Bound)   │
├─────────────────┼─────────────────┼─────────────────┼───────────────────────┤
│ In-App Sandbox  │ Desk Cheat Sheet│ User Guide &    │ Wizards &             │
│ Tutorials       │ (Printable HUD) │ Help Window     │ Mobile Companion      │
│                 │                 │                 │                       │
│ • Zero reading  │ • 2-sec glance  │ • Step-by-step  │ • Step-by-step setup  │
│ • Green ring    │ • Keycaps       │   troubleshoot  │ • Phone Wi-Fi pairing │
│ • Safe mockup   │ • Visual layout │ • Searchable    │ • Vault coordinates   │
└─────────────────┴─────────────────┴─────────────────┴───────────────────────┘
```

1. **Tier 1: First 10 Minutes (Interactive Sandbox Tutorials)**
   * *Mechanism*: `ui/tutorials/` launched from `ui/help_dialogs.py`.
   * *Experience*: Live pulsing focus rings on UI widgets, action-driven validation (e.g. "Click specimen 1001"). Zero passive reading. Data is loaded into an isolated in-memory sandbox (`SandboxManager`) where mistakes cannot harm real files.
2. **Tier 2: At The Desk (Printable Desk Cheat Sheet & Interactive HUD)**
   * *Mechanism*: Printable 1-page quick-reference sheet and in-app dynamic HUD (`show_shortcuts`, `F1`).
   * *Experience*: Big visual keycaps (`[ Ctrl + Enter ]`), dual-depth Excel translation bridge (`Observation!Reviewed = TRUE`), high-contrast badge colors, glanceable in 2 seconds while holding a specimen sheet with both hands.
3. **Tier 3: When Stuck (Trainee Manual & In-App Help Center)**
   * *Mechanism*: `USER_GUIDE.md` rendered inside `ui/help_dialogs.py` (`show_main_help`, `open_help_window`).
   * *Experience*: In-app markdown viewer with chapter jump dropdown, task-oriented headings, dual-depth Excel bridge callouts, and troubleshooting FAQs.
4. **Tier 4: Task-Bound Context (Wizards & Mobile Companion)**
   * *Mechanism*: `ui/create_collection_dialog.py`, `ui/mobile_dialog.py`, and phone web app (`backend/mobile_server.py`).
   * *Experience*: Contextual step-by-step walkthroughs presented at the exact moment of execution (e.g., creating a new collection, updating storage coordinates in vault aisles).

---

## 📖 Canonical Trainee Lexicon

To maintain complete clarity across all dialogs, tooltips, manuals, and cheat sheets, all documentation and future code comments **MUST strictly adhere to these canonical terms**. Technical jargon and internal architectural names are banned from user-facing surfaces.

### 1. Banned Technical Jargon vs. Canonical Trainee Terms

| ❌ Banned Tech Term | ✅ Canonical Trainee Term | Plain-Language Definition / Metaphor |
| :--- | :--- | :--- |
| **Object List / Treeview / QTreeWidget** | **Specimen Directory** | The left-hand panel showing all your specimen cards like a card catalog. |
| **Commit / Validate / Mutate** | **Mark Reviewed / Save Edits** | "Mark Reviewed" confirms you checked the physical sheet. "Save" writes changes. |
| **Provenance (for Storage)** | **Storage Location** | Where the plant physically lives in the museum (Building, Floor, Cabinet, Shelf). |
| **Provenance (for History)** | **Collection History / Ledger Notes** | Who found the plant, when, and where. |
| **Schema / DDL / Relational Join** | **Workbook Layout / Linked Sheets** | How the 4 sheets inside the Excel file share the same Specimen ID. |
| **REST API / Daemon / Background Server** | **Phone Connector / Background Assistant**| The built-in assistant that talks to your phone without any internet setup. |
| **Serialization / Pickling / Dumping** | **Saving to File** | Writing your work safely onto your computer's hard drive. |
| **Nomenclature / Taxonomic Hierarchy** | **Plant Names & Family Tree** | The official scientific names for the plant family, genus, and species. |
| **Primary Key / Unique Identifier** | **Specimen ID / Accession Number** | The unique catalog number printed on the specimen label or sheet. |
| **System GUID / UID** | **Safety Fingerprint** | An 8-letter code Arbor gives each record to prevent accidental sheet mix-ups. |
| **Telemetry / Status Bar** | **Bottom Progress Bar** | The strip at the bottom showing how many specimens you have finished. |
| **Focus Mode / Headless Mode** | **Distraction-Free Mode / Focus View** | Collapsing extra panels so you only see the fields that need attention. |
| **Discrepancy / Taxonomic Conflict** | **Mismatched Information** | When the old handwritten book, modern catalog, or online database disagree. |
| **Backup / Snapshot** | **Safety Backup** | An automatic copy made before big imports so you never lose work. |

---

### 2. Standardized Status Badges (The 8 Single-Badge Rules)

Arbor enforces a **single-badge discipline**: each card in the Specimen Directory displays at most **one** high-contrast priority badge to avoid overwhelming the trainee.

```
┌───────────┬───────────────┬───────────┬─────────────────────────────────────────────────┐
│ Badge     │ Canonical Name│ Color     │ Plain Trainee Meaning & Action Needed           │
├───────────┼───────────────┼───────────┼─────────────────────────────────────────────────┤
│ [ TAX ]   │ Taxonomy Issue│ Coral Red │ Plant name spelling or classification problem.   │
│           │               │ (#c93a40) │ Action: Check label spelling or use GBIF lookup.│
├───────────┼───────────────┼───────────┼─────────────────────────────────────────────────┤
│ [ PROV ]  │ Origin Issue  │ Warm Amber│ Missing collector, date, or locality details.   │
│           │               │ (#d9a036) │ Action: Transcribe missing label field or ?m.   │
├───────────┼───────────────┼───────────┼─────────────────────────────────────────────────┤
│ [ BOX ]   │ Storage Issue │ Earth Brown│ Cabinet, shelf, box, or folder label flag.     │
│           │               │ (#795548) │ Action: Update physical storage location dropdown│
├───────────┼───────────────┼───────────┼─────────────────────────────────────────────────┤
│ [ IMG ]   │ Photo Flag    │ Ocean Blue│ Attached photo missing, blurry, or unlinked.    │
│           │               │ (#0284c7) │ Action: Check camera scan or link local folder. │
├───────────┼───────────────┼───────────┼─────────────────────────────────────────────────┤
│ [ CFCT ]  │ Conflict Flag │ Slate Blue│ Old ledger book or online data disagrees.       │
│           │               │ (#4a7b9d) │ Action: Press Ctrl+H to compare sources.        │
├───────────┼───────────────┼───────────┼─────────────────────────────────────────────────┤
│ [REV+ERR] │ Reviewed Note │ Ochre Gold│ Verified physically, but a known issue remains. │
│           │               │ (#F57C00) │ Meaning: "Curator checked sheet; flag kept."    │
├───────────┼───────────────┼───────────┼─────────────────────────────────────────────────┤
│ [ REV ]   │ Done / Checked│ Herb Green│ Fully reviewed, clean, and verified specimen.   │
│           │               │ (#3a7d44) │ Action: Done! Move to the next sheet.           │
├───────────┼───────────────┼───────────┼─────────────────────────────────────────────────┤
│ [ UNREV ] │ To-Do / New   │ Cool Gray │ New or pending specimen waiting for review.     │
│           │               │ (#757d77) │ Action: Inspect sheet and verify details.       │
└───────────┴───────────────┴───────────┴─────────────────────────────────────────────────┘
```

---

### 3. The 4 Directory Card Layout Profiles

Trainees work on different computer screens (13-inch laptops, desktop curation monitors). Arbor provides 4 one-click layout profiles (`Settings` $\rightarrow$ `Appearance` $\rightarrow$ `Card Profiles` or `Ctrl+Shift+1..4`):

1. **Standard (`78px`)**:
   * *Trainee Description*: **Everyday Balanced View**.
   * *What it shows*: Specimen ID, italic plant name, single status badge, and a summary line (Family, photo count, loan status). Default view for desktop monitors (~12 cards visible).
2. **Compact (`64px`)**:
   * *Trainee Description*: **High-Speed List (Laptop Friendly)**.
   * *What it shows*: Condensed rows, smaller text, packed layout. Ideal for smaller laptop screens (~15 cards visible) when rapidly checking through boxes.
3. **Full Details (`92px`)**:
   * *Trainee Description*: **Full Research View**.
   * *What it shows*: Generous spacing, author citations (e.g. *Quercus robur L.*), expanded storage location (Building/Floor/Cabinet/Shelf), and full metadata chips.
4. **Minimalist**:
   * *Trainee Description*: **Distraction-Free Card**.
   * *What it shows*: Stripped-down card showing strictly the Accession ID and botanical name without badges or photo counters. Ideal for pure label typing.

---

### 4. ICEDIG Missing Data Codes (Standard Label Shortcuts)

When transcribing damaged or historic 100-year-old labels, trainees must never leave ambiguous blank fields. Arbor uses standard international museum shortcuts:

| Trainee Keyboard Shortcut | Quick Code | Plain-Language Meaning | Example Use Case |
| :--- | :--- | :--- | :--- |
| `Ctrl+Shift+M` | `?m` | **Missing on Label** | Label has no collector written on it. |
| `Ctrl+Shift+I` | `?i` | **Cannot Read / Damaged** | Ink is water-damaged, faded, or torn. |
| `Ctrl+Shift+U` | `?u` | **Skipped For Now** | Information skipped during initial pass. |
| `Ctrl+Shift+W` | `?w` | **Confidential / Protected** | Endangered plant location kept secret. |
| `Ctrl+Shift+Backspace` | *(None)* | **Clear Field** | Erases any value in the field. |

---

## 🗺️ Master Touchpoint Matrix

Every feature in Arbor must be supported across all four user-assistance touchpoints. If a feature exists in code but is missing from any column, documentation drift has occurred.

| Core Feature & Workflow | (a) In-App Tutorial Step (`ui/tutorials/`) | (b) In-App Help & Tooltips (`ui/unified_settings.py`) | (c) Desk Cheat Sheet (`Desk HUD`) | (d) Trainee Manual (`USER_GUIDE.md`) | (e) Context Wizard or Mobile (`ui/`) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Navigating Specimen Cards** | `select_object`: Step 1 of Review Tutorial (click card 1001) | Tooltip: "Navigate using Arrow keys or Command Palette" | **`Left` / `Right`**: Previous / Next<br>**`Up` / `Down`**: Browse list | **Chapter 1 & 9**: Specimen Directory navigation rules | Mobile companion bottom swipe & next-record buttons |
| **2. Inspecting High-Res Scans** | Part of Step 2: photo pane inspection | Tooltip: "Image resampling algorithms (Lanczos vs Bilinear)" | **`Alt+R`**: Rotate 90°<br>**`Ctrl+Plus/Minus`**: Zoom<br>**`Ctrl+0`**: Reset | **Chapter 1 & 9**: Image Viewport, zoom gestures, trackpad pan | Mobile photo pinch-to-zoom and external browser popout |
| **3. Checking Label Data (Form)** | `inspect_editor`: Step 2 of Review Tutorial | Tooltip: "Registration form fields and strict validation" | **`Ctrl+E` / `Ctrl+I`**: Jump to form<br>**`Ctrl+Z` / `Ctrl+Y`**: Undo/Redo | **Chapter 1 & 4**: Registration Editor & taxonomic metadata | Mobile label editor with auto-capitalization |
| **4. Marking Specimen as Done** | `mark_reviewed`: Step 4 of Review Tutorial (Ctrl+Enter) | Tooltip: "Mark as Reviewed timestamps name and date in Log" | **`Ctrl+Enter` / `Ctrl+R`**: Mark Reviewed (Green Button) | **Chapter 4 & 9**: The Review Workflow & green checkmarks | Big green **[ ✓ Mark Reviewed ]** button on phone UI |
| **5. Flagging Quality Problems** | `check_flags`: Step 3 of Review Tutorial | Tooltip: "Problem flags record quality issues in Observation sheet"| **`Space`**: Toggle problem box<br>**`Shift+Up/Down`**: Pick problem | **Chapter 4 & 10**: The 11 standard problem checkboxes | Mobile quick-toggle pills for illegible / damaged |
| **6. Fixing Mismatched Ledgers** | Step 1-4 of Discrepancy Tutorial (`open_resolver`) | Tooltip: "Auto-advance history navigates to next conflict" | **`Ctrl+H`**: Open Conflict Resolver | **Chapter 4**: Comparing active catalog vs ledger books vs GBIF | Mobile conflict alert banner highlighting differences |
| **7. Checking Global Names (GBIF)** | Covered in Discrepancy Tutorial (`select_resolution`) | Non-blocking toast alert: "Exact GBIF match" / "Fuzzy match" | Menu: **🌿 Tools $\rightarrow$ GBIF Lookup** | **Chapter 4**: Online taxonomic verification without errors | Mobile GBIF status indicator badge |
| **8. Finding Specimens Quickly** | Step 1 of Review Tutorial: typing in search box | Tooltip: "Instant typo-tolerant search across ID and taxon" | **`Ctrl+F`**: Search Bar<br>**`Ctrl+K`**: Omni-Bar | **Chapter 3 & 6**: Fast searching, ID prefix (`#1042`) | Mobile instant search and barcode input |
| **9. Recording Storage Locations** | Step 4 of Database Tutorial | Tooltip: "Compact 2-row location layout in center view" | **`Ctrl+L` / `F4`**: Jump to Storage<br>**`Ctrl+Alt+K`**: Apply Preset | **Chapter 1 & 10**: Building, Floor, Cabinet, Shelf | Mobile physical coordinate steppers (+ / - buttons) |
| **10. Creating New Collections** | Step 1 of Database Tutorial (`open_db_wizard`) | Step-by-step expanders `[?]` in Create Collection dialog | Menu: **File $\rightarrow$ + New Collection** | **Chapter 10**: The 4-Sheet botanical collection architecture | `CreateCollectionDialog` with 1-click template button |
| **11. Phone Barcode Companion** | Mentioned in Help Center options list | Tooltip: "Require PIN authentication for phone companion" | Menu: **📱 Mobile $\rightarrow$ QR Code** | **Chapter 5**: Phone pairing, Eduroam bypass, vault mode | Onscreen QR code modal with Cloudflare tunnel switch |
| **12. Changing Card Looks** | Visual layout controls in Settings Appearance | Tooltip: "Density profiles: Compact 64px, Standard 78px" | **`Ctrl+Shift+1..4`**: Card Profiles | **Chapter 1**: Dual view modes and Directory Card Personas | Mobile theme auto-sync (light/dark mode) |
| **13. Missing Data Codes (ICEDIG)** | Mentioned in Trainee Manual Chapter 8 | Tooltip: "Insert standardized missing data tokens" | **`Ctrl+Shift+M`**: `?m`<br>**`Ctrl+Shift+I`**: `?i` | **Chapter 8**: When and how to record illegible labels | Mobile settings modal ICEDIG quick-reference table |
| **14. Safety Backups & Recovery** | Handled transparently by `SandboxManager` | Tooltip: "Timestamped backups in backups/ before Excel import" | **`Ctrl+S`**: Save Workbook | **Chapter 10 & 11**: Automatic backups and session recovery | Mobile automatic save-on-disconnect safeguard |

---

## 🎓 The 4-Tier Progressive Disclosure Curriculum

### Tier 1: The First 10 Minutes (Interactive Sandbox)
* **Goal**: Enable a brand-new trainee to inspect and review their first specimen within 10 minutes without reading a single page of text.
* **Mechanism**:
  1. Trainee clicks **`❓ HELP ▾`** $\rightarrow$ **`Tutorial: Reviewing Objects`** (or clicks Help on first launch).
  2. The application takes an in-memory snapshot of the workbook and loads a 3-specimen practice scenario.
  3. A high-contrast pulsing ring surrounds the search bar: *"Step 1: Click on specimen 1001 in the list."*
  4. The trainee clicks the card; the ring jumps to the registration form: *"Step 2: Check the plant name on the label."*
  5. The ring jumps to the green button: *"Step 3: Press Ctrl+Enter or click '✓ Mark as Reviewed'."*
  6. On finish, Arbor exits the sandbox and restores the user's workspace untouched.

### Tier 2: At The Desk (The 1-Page Cheat Sheet)
* **Goal**: Keep both hands free for physical specimen sheets while providing instant keyboard guidance.
* **Format**: A printable physical A4 / Letter reference card kept beside the keyboard, mirrored by the in-app `F1` HUD.
* **Key Visual Elements**:
  * **Big Action Keycaps**: `[ Ctrl ]` + `[ Enter ]` = Mark Reviewed.
  * **Movement Keys**: `[ ← ]` / `[ → ]` = Previous / Next plant.
  * **Status Badge Colors**: Red = Name Problem, Green = Finished, Gray = To-Do.
  * **Quick Codes**: `?m` = Missing, `?i` = Illegible.

### Tier 3: When Stuck (In-App Help & Manual)
* **Goal**: Provide answers to common hurdles within 30 seconds without needing an IT technician or senior curator.
* **Structure of `USER_GUIDE.md` / `HelpWindow`**:
  * Organized by **Curator Goals** rather than software components (e.g., "What to do when handwriting is cut off" instead of "Unvalidated_source Schema").
  * Step-by-step numbered instructions (1, 2, 3).
  * Clear troubleshooting sidebars (*"If the photo does not load, press `F8` to toggle the image panel"*).

### Tier 4: Task-Bound Wizards & Mobile Companion
* **Goal**: Provide contextual guidance for specialized or physical tasks.
* **Contexts**:
  * **Starting a New Project**: `CreateCollectionDialog` features clean expandable cards for Sheet 1 (Catalog), Sheet 2 (Problems & Storage), and Sheet 3 (Audit Log), with green "🌱 For New Curators" summaries.
  * **Auditing in Vault Aisles**: The phone companion displays large finger-friendly steppers (`+` / `-`) for cabinet numbers and a barcode scanner button that beeps softly on a successful scan.

---

## ✍️ Plain-Language Style Guide for Authors & Agents

Whenever writing a tooltip, dialog message, error alert, or guide chapter for Arbor, follow these six non-negotiable rules:

1. **Write for an 8th-Grade Reading Level**:
   * *Instead of*: "Initiates asynchronous synchronization of in-memory mutations with the underlying persistent storage."
   * *Write*: "Saves your changes to the Excel file so your work is safe."
2. **Explain the 'Why' Before the 'How'**:
   * *Instead of*: "Clicking this button sets `Reviewed = True` and records `ReviewedAt = ISO8601`."
   * *Write*: "Click 'Mark Reviewed' when you have finished checking the physical sheet. Arbor stamps your name and the date into the audit log."
3. **Use Physical Museum Metaphors**:
   * Refer to "Specimen cards in a drawer", "Sheets in a folder", "Cabinets in the vault", and "Checking off items on your to-do list".
4. **Never Blame the User in Error Messages**:
   * *Instead of*: "Invalid input format: ObjectID cannot be null."
   * *Write*: "Please enter a specimen number before saving. Every plant needs an ID number."
5. **Keep Action Steps Under 4 Sentences**:
   * Trainees scan rather than read. Break instructions into bulleted steps starting with active verbs (*Click*, *Press*, *Check*, *Type*).
6. **Use Keycap Formatting for Shortcuts**:
   * Always write `Ctrl+Enter`, `Ctrl+S`, `F1`, and `Esc` inside backticks or keycap brackets so they stand out immediately.

---

## 🔍 Documentation Maintenance & String Audit Protocol

To guarantee that documentation never drifts from code:

1. **Audit Checklist for Pull Requests and Code Changes**:
   * [ ] Does the change introduce a new keyboard shortcut? $\rightarrow$ Update Cheat Sheet, `ui/help_dialogs.py` HUD, and `USER_GUIDE.md`.
   * [ ] Does the change rename or add a badge? $\rightarrow$ Verify against the 8 Canonical Badges above.
   * [ ] Does the change alter settings? $\rightarrow$ Ensure plain-language text exists in `SETTING_INFO_TEXTS`.
   * [ ] Has an entry been added to `documentation/CHANGE_JOURNAL.md`?
2. **Automated Vocabulary Grep**:
   * Run searches across `ui/` for banned strings (`schema`, `REST API`, `daemon`, `nomenclature`, `relational join`). If found in user-facing labels, replace with the canonical equivalent.

---

## ⚡ The 1-Prompt Sync Protocol

When future features, shortcuts, or layout modes are added to Arbor, the project owner or lead curator can execute the following standardized prompt in any AI agent session to synchronize all documentation automatically:

```markdown
Run the Arbor 1-Prompt Documentation Sync Protocol:
1. Read `documentation/CHANGE_JOURNAL.md` to identify all unreleased and recent user-facing delta entries.
2. Review `documentation/MASTER_DOCUMENTATION_MAP.md` to ensure strict compliance with the Canonical Trainee Lexicon and 4-Tier Curriculum.
3. Update `USER_GUIDE.md` to incorporate all new features, settings, shortcuts, and workflows into their respective chapters.
4. Verify that in-app touchpoints (`ui/help_dialogs.py` shortcuts list, `ui/unified_settings.py` SETTING_INFO_TEXTS, and `ui/command_palette.py` action hints) match the updated manual.
5. Move the processed items in `documentation/CHANGE_JOURNAL.md` under a dated release header and mark the Documentation Sync Checklist items as complete [x].
```
