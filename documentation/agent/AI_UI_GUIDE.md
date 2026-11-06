---
name: Arbor
colors:
  surface: '#fbfaf8'
  surface-dim: '#dadada'
  surface-bright: '#fbfaf8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f5f1'
  surface-container: '#e9ece5'
  surface-container-high: '#e9ece5'
  surface-container-highest: '#e9ece5'
  on-surface: '#2c302e'
  on-surface-variant: '#757d77'
  inverse-surface: '#181c19'
  inverse-on-surface: '#e8ebe9'
  outline: '#757d77'
  outline-variant: '#8b948d'
  surface-tint: '#5e5e5e'
  primary: '#2c302e'
  on-primary: '#ffffff'
  primary-container: '#1b1b1b'
  on-primary-container: '#848484'
  inverse-primary: '#c6c6c6'
  secondary: '#3a7d44'
  on-secondary: '#ffffff'
  secondary-container: '#adf0a6'
  on-secondary-container: '#326f34'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#1c1b1b'
  on-tertiary-container: '#868383'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2e2e2'
  primary-fixed-dim: '#c6c6c6'
  on-primary-fixed: '#1b1b1b'
  on-primary-fixed-variant: '#474747'
  secondary-fixed: '#b0f3a9'
  secondary-fixed-dim: '#95d68f'
  on-secondary-fixed: '#002204'
  on-secondary-fixed-variant: '#13521a'
  tertiary-fixed: '#e6e1e1'
  tertiary-fixed-dim: '#c9c6c5'
  on-tertiary-fixed: '#1c1b1b'
  on-tertiary-fixed-variant: '#484646'
  background: '#fbfaf8'
  on-background: '#2c302e'
  surface-variant: '#e2e2e2'
  status-red: '#c93a40'
  status-green: '#3a7d44'
  status-yellow: '#d9a036'
  status-blue: '#4a7b9d'
  search-orange: '#d95c14'
  border-hairline: '#C4C7C7'
  surface-header: '#F3F3F3'
typography:
  headline-lg:
    fontFamily: Lora
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Lora
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  section-header:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '700'
    lineHeight: 22px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 12px
  margin-main: 24px
---

# AI UI Design & Development Guide for Arbor

Welcome, AI Agent! This document acts as the single source of truth for **all user interface (UI) enhancements, upgrades, and modifications** in Arbor. When asked to change or expand the program's UI, you **MUST** read, respect, and build according to the visual philosophy, design tokens, structural layouts, and programming constraints documented below.

---

## 1. Core Visual Philosophy & Design Intentions

Arbor is an archival tool designed for **academic precision, simplicity, and clarity**. Its visual layout serves high-stakes botanical curation and must maintain three main pillars:
1. **Intuitive:** The interaction model must be instantly comprehensible. Common pathways (editing a record, reviewing images, resolving conflicts) should feel natural, accessible, and flow logically.
2. **Simple:** Keep cognitive load low. Only show what is necessary to complete the task at hand. Avoid unnecessary visual noise, excessive decorations, or cluttered controls.
3. **Clean:** Maintain precise alignment, consistent typography, flat depths, and clear semantic layouts.

### Laptop & Compact Screen Optimization
Arbor is frequently utilized in professional environments on **laptops and smaller displays**. All design updates must strictly support laptop views by utilizing:
- **Collapsible Elements & Focus Modes:** Provide smart toggling or automatic vertical collapse when space is limited.
- **Scrollable Tiers:** Dynamic metadata areas and checklist blocks should reside within well-bounded scrollable canvases so they never push buttons or headers off the viewport.
- **Dynamic Card-Level Visibility:** Form sections must group logically inside individual container blocks (cards) that automatically contract or hide themselves when internal fields are not active or in Focus Mode.

---

## 2. Design System & Design Tokens

Arbor's aesthetic is **Modern, Simple, Clean, and Professional**. Use the following tokens explicitly when writing code or configuring styles.

### A. Color Palette
- **Primary & Neutral Canvas:** Core commands and structural headers use Charcoal (`#2c302e`). The general workspace uses Warm Alabaster (`#fbfaf8`) to reduce fatigue, while the active workspace cards use pure White (`#ffffff`) to stand out.
- **Semantic Indicators (Validation & Alerts):**
  - **Brick Red (`#c93a40`):** Critical errors, missing mandatory values, or flagged problems.
  - **Vibrant Fern (`#3a7d44`):** Verified data, completed audits, or successful reviewed states.
  - **Mustard Yellow (`#d9a036`):** Warning states, pending discrepancies, or unsaved drafts.
  - **Slate Blue (`#4a7b9d`):** Versioning conflicts, historical discrepancies, or external database queries.
- **Accents:** Secondary branding utilizes a Vibrant Fern (`#3a7d44`), and an Ember Orange (`#d95c14`) is reserved exclusively for query highlighters and active search states.

### B. Typography
Arbor utilizes a **tri-font strategy** to clearly distinguish between literary nomenclature, systematic data, and technical metadata:
1. **Scholarly Serif (Lora / Georgia):** Used for primary page titles, main specimen headers, and botanical names. It highlights the historical, academic significance of the museum collection.
2. **Systematic Sans (Inter / Arial / Helvetica):** The primary workhorse font for metadata forms, inputs, field labels, and general interactive UI text. This keeps labels clear on smaller laptop views.
3. **Technical Monospace (JetBrains Mono / Consolas):** Reserved for specimen IDs, coordinate strings, technical status indicators, and keyboard shortcut reminders. It ensures numbers line up perfectly.

### C. Layout, Elevation, & Shapes
- **Depth and Layering:** Arbor does not use fuzzy ambient shadows. Depth is communicated through **Tonal Layers** (using background contrasts like `#f3f3f3` vs `#ffffff`).
- **Shapes:** Shape language is clean and structural. Elements use a soft 2px (or `0.25rem` / `sm: 0.125rem` for tiny badges) radius on buttons and fields to feel precise and professional.
- **Spacing Rhythm:** Form paddings utilize a cohesive base unit system to keep spacing logical and clean.

---

## 3. Structural Layers of the Existing UI

To keep layout changes safe and cohesive, you must understand Arbor's existing layout layers inside `ui/main_window.py`:

```
+---------------------------------------------------------------------------------------------------------+
| LAYER 1: Navigation Topbar                                                                              |
| [arbor Title] | [FILE] [NAVIGATE] [IMAGES] [CREATE] [HISTORY] ... [Online Status] [Unsaved Badge]       |
+---------------------------------------------------------------------------------------------------------+
| LAYER 2: Inline Banner (Hidden by default; packs dynamically for success/warning notifications)         |
+---------------------------------------------------------------------------------------------------------+
| LAYER 3: Main Split-Pane Workspace (Fills remaining height)                                             |
|                                                                                                         |
|  +------------------------+  +----------------------------------+  +---------------------------------+  |
|  | LEFT PANEL (Treeview)  |  | CENTER PANEL (Visual Workspace)  |  | RIGHT PANEL (Metadata Audit)    |  |
|  |                        |  |                                  |  |                                 |  |
|  | - Sort & Filter bar    |  | - Specimen Title Header          |  | - Specimen Audit Tab            |  |
|  | - Live Search Bar      |  | - Image Status and Counts        |  |   - Taxonomy Card (🧬)          |  |
|  | - Object list treeview |  | - Image Toolbar (Zoom/Rotate)    |  |   - Collection Card (📦)        |  |
|  | - Collapsible Location |  | - Scrollable Image Canvas        |  |   - Notes Card (📝)             |  |
|  |   Frame (Bottom side)  |  |                                  |  | - Problem Flags Tab             |  |
|  |                        |  |                                  |  | - Sticky "Mark Reviewed" Button |  |
|  +------------------------+  +----------------------------------+  +---------------------------------+  |
|                                                                                                         |
+---------------------------------------------------------------------------------------------------------+
| LAYER 4: Global Status Bar & Stats (Bottom edge)                                                        |
+---------------------------------------------------------------------------------------------------------+
```

### Dynamic Fields and Sections Configuration
Rather than hardcoding input boxes, Arbor reads field schemas directly from `config.py` under `DATABASE_CONFIGS`. The registration inputs, dropdown choices, location configurations, and problem validators are constructed dynamically. When asked to modify, add, or alter fields, **always edit `config.py` instead of hardcoding raw UI widgets**.

---

## 4. Key Design Patterns & Golden Standards

When designing new interfaces, look to the following existing modules as the absolute standard of excellence in the Arbor codebase:

### A. The "Historical Discrepancies" Window (`ui/historical_resolver.py`) - **GOLD STANDARD**
This is the most visually refined window in the codebase. It uses a master-detail split layout optimal for laptop curation:
- **Left Sidebar ("Field Directory"):** Acts as a clear vertical index. Each field has a color-coded status indicator tag (e.g., `ERR` in Red, `UKN` in Yellow, `CFCT` in Blue) so user-attention is immediately drawn to discrepancies.
- **Scrollable Cards (Main Area):** Resolves fields using distinct container cards. Each card clearly frames the "Current Value" next to "Historical Suggestions" (which are styled as flat, clickable buttons for instant population) and a "Manual Entry" input.
- **Side Overlapping Section Labels:** Small uppercase metadata headers are beautifully placed to overlap container bounds, saving valuable vertical screen real estate.

### B. Specimen Audit Cards (`ui/main_window.py`)
Metadata registration fields in the main workspace are grouped into three thematic cards:
1. **Taxonomy & Scientific Name** (🧬)
2. **Collection & Specimen Metadata** (📦)
3. **Audit Notes & Descriptions** (📝)

**Dynamic Reflow Rule:** If Focus Mode is activated, these card containers dynamically hide their entire blocks if all internal fields are hidden. This maintains a clean form layout on laptop displays.

### C. Adaptive Focus Mode & Validation Warnings
- **Adaptive Inputs:** When a problem flag (e.g., `Genus_Problem`) is checked, the left border bar of that field shifts to a solid 3px Red accent bar, and the field's text label shifts to a Red warning color.
- **Soft Tints:** Validation checks dynamically color warning text fields with a soft Yellow or soft Red tint when values are erroneous or logically conflicting, calling the user's attention to the exact input without throwing intrusive alert dialogs.

---

## 5. Programming Constraints & Implementation Rules

To maintain Arbor's high-performance architecture, all AI agents **MUST** follow these strict programming rules.

### Rule 1: High-Performance Data Access (Pandas)
Arbor is designed to load and parse large botanical databases near-instantaneously.
- **No loops over DataFrame indexes:** Never use `.iterrows()` or make individual `.loc[]` index queries inside Treeview list updates or rendering loops. This introduces massive CPU overhead due to pandas Series creation.
- **The Dictionary Rule:** Pre-convert DataFrame columns into standard python dictionary structures (using `.to_dict()`) outside loops and perform high-speed $O(1)$ dictionary lookups instead.
- **Use `.itertuples()`:** If DataFrame iteration is mandatory, always use `.itertuples()` instead of `.iterrows()`. It runs up to 15 times faster.

### Rule 2: UI Font & Coordinate Scaling (DPI)
Arbor is executed on high-resolution, variable-DPI displays.
- **Always Wrap with `sc()`:** Never use hardcoded pixel integers for font sizes, paddings, column widths, widget heights, or layout boundaries.
- **Correct Usage:** Always scale layout metrics by wrapping them in the config helper function `sc(...)`.
  - *Incorrect:* `font=("Inter", 12)` or `width=100`
  - *Correct:* `font=("Inter", sc(12))` or `width=sc(100)`

### Rule 3: Single-Threaded Tkinter Event Loop (BackgroundWorker & EventBus)
- **Non-blocking Operations:** Heavy tasks, image fetching, and database operations must **never** block the mainloop. Use the centralized `BackgroundWorker` (via `app_worker.run_in_background()` in `backend/task_queue.py`) for heavy workloads, allowing it to schedule completion callbacks back on the main thread automatically.
- **Event-Driven UI Updates:** Do not hard-couple UI components. Use the `EventBus` (`ui/state.py`) to broadcast state changes (`app_bus.publish()`). Components should subscribe to relevant events and update themselves safely.
- **Eager Error Capturing:** When scheduling deferred callbacks (e.g., `self.root.after`) inside exception handling blocks, capture the target exception message or traceback eagerly using default argument parameters (e.g., `lambda em=err_msg: ...`) rather than referencing free variables from the deleted exception scope to avoid silent `NameError` exceptions.
- **`app_bus.publish()` Thread Marshaling:** Never call `app_bus.publish()` from a background thread directly. All publishes from background threads must be dispatched to the main thread first: `root.after(0, lambda: app_bus.publish(...))`.
- **Subscriber Lifecycle:** All `app_bus.subscribe()` calls must be paired with cleanup. Use `app_bus.subscribe_managed(widget, event_type, callback)` which automatically unsubscribes when the widget is destroyed. Do NOT use bare `app_bus.subscribe()` for widget-bound callbacks.
- **Raw Threads Prohibited for One-Shot Tasks:** Never use `threading.Thread(target=...).start()` for one-shot background operations (file I/O, data exports, API calls). Always use `app_worker.run_in_background(func, success_callback, error_callback)`. Raw `threading.Thread` is only acceptable for long-lived persistent loops, such as the `MobileServer` Flask serving thread.

### Rule 4: Component Decoupling (`unified_settings.py` vs `main_window.py`)
- Arbor is actively moving away from monolithic UI structures (like the 7000+ line `ui/main_window.py`).
- When modifying settings, use the modular structure defined in `ui/unified_settings.py` instead of adding logic to deprecated monolithic files. New UI panels should be built as independent classes that interact via the `EventBus`.
- **`unified_settings.py` Status:** `UnifiedSettingsWindow` is a partially-migrated component. Its `_push_layout_to_app()` method still directly calls methods on `self.app` (legacy pattern). Do **not** use this as a reference for new component communication. New settings panels or components must communicate exclusively via `app_bus.publish(SETTINGS_CHANGED, key=..., value=...)` and subscribe to events rather than calling methods on `ObjectProgramUI` directly.
- **`live_callbacks` is a Legacy Pattern:** The `live_callbacks` dict passed to `UnifiedSettingsWindow` is a transitional mechanism. New components should not introduce `live_callbacks`-style direct callback wiring. Use EventBus events instead.

### Rule 5: Compact Form Serialization (Autosaves)
- **Use `.autosave.json`:** Temporary background sessions are serialized into the secure JSON format (`.autosave.json`). Ensure any custom UI state is serializable or properly decoupled from visual Tkinter widgets.
- **Edit Source, Not Artifacts:** If a file is a compiled build artifact, do not edit it directly. Trace the code back to its Python source under the `ui/` directory and recompile accordingly.

---

## 6. Template: User Intentions Behind UI Designs

*This section is dedicated to capturing user-specific UI layout guidelines and design goals. AI agents should reference this section to align with the core visual strategy requested by the owner.*

- **Design Philosophy:** Keep the interface clean, simple, and straightforward. Users are handling large collections of dry, textual botanical specimens. The UI should act as a silent, efficient assistant.
- **Color Accent Intention:** Do not over-saturate layouts. Use soft, non-glare off-whites on the main panel background to minimize visual fatigue. Reserved intense accent colors (Status Red, Search Orange) must be used sparingly to draw the user's eyes specifically to actionable items.
- **Symmetry and Alignment:** Maintain strict, consistent visual alignment. Use borders and background panel tones as the primary visual separators. Space forms cleanly and logically.
- **Space and Laptop Preservation:** Make tabs, lists, and tools collapsible or togglable. When users need more screen estate for visual inspection of specimens, the interface must let them hide auxiliary lists or panels without obstructing the core workflow.

---

## 7. Strict Dark Mode, Command Palette & Ergonomics Engineering Rules

To ensure UI consistency across Light and Dark themes, eliminate modal clutter, and prevent future AI agents from introducing regression defects, all future UI code **MUST** adhere to the following contracts:

### Rule 6: Mandatory `set_dark_mode()` Contract on Compound Widgets
- Any compound widget, contextual strip (such as `ObjectContextBar`), or custom container frame added to Arbor **MUST** implement a `set_dark_mode(is_dark: bool)` method and register with `apply_theme()` in `ui/layout_settings.py`.
- **No Unconditional Light Color Literals:** Never write hardcoded `#ffffff`, `#f2f5f1`, `#e9ece5`, or `#2c302e` directly onto Tkinter `Frame`, `Label`, or `Button` widgets without a dark mode condition or token mapping.
- **Active/Success Token Standard:** When indicating reviewed, verified, or completed records in Dark Mode:
  - **Light Mode:** `#ffffff` card with `#3a7d44` text and border.
  - **Dark Mode:** Deep forest container (`#1e3a24`) with vibrant text (`#85e89d`) and `#3a7d44` border. Never animate or configure backgrounds to pure `#ffffff` in Dark Mode.
- **Treeview Contrast (WCAG AA):** Foreground colors in dark Treeview rows (`#212622` / `#181c19`) must maintain high contrast (e.g., `#b0f3a9` for reviewed tags, not dark `#3a7d44`).

### Rule 7: Non-Blocking Floating Toasts Over Modal Dialogs
- Routine operation confirmations (saving sessions, successful GBIF validation matches, toggling review states, copying values) **MUST** use non-blocking floating toasts via `app.show_toast(msg, toast_type)` or `ToastManager.show()`.
- Intrusive `messagebox.showinfo` popups are strictly prohibited for routine, clean curator workflows because they interrupt rapid keyboard navigation. Modal dialogs are strictly reserved for destructive confirmations (`messagebox.askyesno`) and fatal errors (`messagebox.showerror`).

### Rule 8: Universal Command Palette Registration Protocol
- Every new user-facing action, tool, export flow, dialog, or navigation shortcut **MUST** be cataloged in `ui/command_palette.py` under the appropriate category (`SPECIMEN`, `NAVIGATION`, `TOOLS`, `IMAGE`, `PRESETS`, `SESSION`, `HELP`).
- **Specimen Lookup Hook:** Accessing the active database in the command palette must always query `getattr(self.ui, "app", getattr(self.ui, "app_state", None))`. Do not assume `self.ui.app_state` exists.

### Rule 9: Top Navigation Bar Cleanliness & User Preferences
- The top navigation bar (`ui/navigation_bar.py`) is reserved strictly for global menus and compact view management.
- **Secondary Controls Clustered & Hidden by Default:** Auxiliary navigation buttons (`◄`, `►`, `Last`, `⚠ Next Problem`, `Next+Hist`) must be organized into segmented button clusters and hidden by default. Their visibility is controlled via the `show_secondary_nav` toggle in Unified Settings (`prefs.json`).
- **No Fake Status Indicators:** Never introduce static, un-updated status indicators (e.g. dummy `STATUS: ONLINE` canvas dots). Real telemetry belongs exclusively in the 26px status bar at the bottom.

### Rule 10: Supported Data Export Standards
- Arbor's standard data exchange formats are **Excel Workbooks (`.xlsx`)** and **Delimited Spreadsheets (`.csv`)** via `Export Filtered Subset...` (`export_filtered_list`).
- **Darwin Core (DwC) export has been permanently decommissioned and removed.** Do not re-introduce Darwin Core occurrence exporters or references.

---

## 8. Specimen Directory & Curatorial Card Design Standards

To guarantee high visual clarity for curators and instant $O(1)$ responsiveness across datasets of 20,000+ specimens, all directory and card components **MUST** adhere to these strict ergonomic guidelines:

### A. Single-Badge Discipline in Detailed Cards (`ui/widgets.py`)
- **Zero Icon / Emoji Clutter:** Cards must never display multiple stacked badges or emoji icons (`🧬`, `📦`, `📷`, `🌐`).
- **One Category Badge on Row 1:** Each card is assigned exactly one high-contrast status badge formatted in JetBrains Mono at `sc(8)` bold:
  - `[ TAX ]`: Active taxonomy problems (`Taxonomy_Problem`, `Genus_Problem`, `Species_Problem`).
  - `[ PROV ]`: Provenance/collection issues (`Locality_Problem`, `MissingLabel`, `Date_Problem`).
  - `[ BOX ]`: Physical box/plant part problems (`PlantPart_Problem`, `Box_Label_Problem`).
  - `[ IMG ]`: Media problems or missing images.
  - `[ REV+ERR ]`: Specimen is marked reviewed but has unresolved flags.
  - `[ REV ]`: Clean reviewed specimen.
  - `[ UNREV ]`: Unreviewed record in good standing.
- **Inline Metadata Row (Row 2):** Never unpack or repack individual badge widgets on Row 2. All secondary attributes are concatenated into a single, bullet-separated string rendered in a single `Label`:
  ```
  OBJ-0042 • PINACEAE • 2 photos • LOAN • UKN • UNVAL
  ```
  This eliminates Tkinter geometry recalculations (`pack_forget` / `pack`) during scrolling.

### B. $O(1)$ Targeted Card Selection Diffing
- In `redraw_cards_highlights()`, never iterate recursively through all rendered cards in the viewport.
- Maintain `_last_highlighted_oids` and compute the symmetric difference:
  ```python
  changed_oids = (last_highlighted ^ current_selected)
  ```
  Only update background styling (`#ffffff` light / `#2c352e` dark) on the small subset of cards whose selection state actually toggled.

### C. Curatorial Command Strip (`ui/object_context_bar.py`)
- **Accession Pill:** Monospace ID badge (`[ 10482 ]`) paired with live specimen index counter (`42 of 1,250`).
- **Botanical Typography:** Scientific name displayed in *Lora* / *Georgia* italic serif (`sc(12)` italic bold), with author citation in muted regular text.
- **Interactive Status Badge:** Prominent, color-coded pill (`[ TAXONOMY ISSUE ]`, `[ PROVENANCE ERROR ]`, `[ ✓ REVIEWED ]`) that binds to `<Button-1>` to launch relevant problem resolvers directly.
- **Dirty State Dot:** An amber `● Unsaved` indicator dynamically shows whenever `app.dirty` is true, disappearing immediately when saved.
- **Emoji-Free Action Buttons:** Action controls (`[ GBIF Verify ]`, `[ Books (N) ]`, `[ Send to Phone ]`) must use clean archival text labels.

### D. Sidebar Drawer Sashing & Easing Lifecycle (`ui/main_window.py`)
- **Cubic Ease-Out Transition:** Sidebar expansion and collapse animations must use a cubic ease-out curve ($1 - (1 - t)^3$) over 120ms at ~12ms ticks (~80 FPS).
- **Flicker-Free Unmapping Sequence:** Never call `left_content_frame.pack_forget()` before starting an animation. Only unmap the frame inside the `on_complete` callback *after* the sash transition reaches the collapsed boundary (`sc(40)`).
- **Width Persistence & Ergonomics:**
  - Collapsed rail width: `sc(40)`.
  - Default expanded width: `max(sc(320), sc(360))`.
  - User dragged sash width must persist in `prefs["sidebar_width"]` so expanding restores the curator's preferred layout.

### E. Centralized, Non-Destructive Mousewheel Scroll Standard (`ui/scroll_helper.py`)
- **Strictly Prohibit Global `bind_all("<MouseWheel>")` / `unbind_all` Hooks:** Never call `bind_all("<MouseWheel>")` or `unbind_all("<MouseWheel>")` on `<Enter>`/`<Leave>` of scrollable frames or in `<Destroy>` handlers. Doing so overrides or permanently unbinds scrolling in parent and overlapping windows.
- **Use `ui.scroll_helper.bind_mousewheel(canvas, frame)`:**
  ```python
  from ui.scroll_helper import bind_mousewheel
  bind_mousewheel(canvas, scrollable_frame)
  ```
  This attaches a canvas-specific bindtag that recursively applies to all children without altering global event bindings.
