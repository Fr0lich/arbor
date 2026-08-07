---
name: Arbor
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#4c4546'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f1f1f1'
  outline: '#7e7576'
  outline-variant: '#cfc4c5'
  surface-tint: '#5e5e5e'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#1b1b1b'
  on-primary-container: '#848484'
  inverse-primary: '#c6c6c6'
  secondary: '#2e6b30'
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
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
  status-red: '#C62828'
  status-green: '#2E7D32'
  status-yellow: '#FBC02D'
  status-blue: '#0284C7'
  search-orange: '#D9480F'
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
- **Primary & Neutral Canvas:** Core commands and structural headers use solid Black (`#000000`). The general workspace uses a soft, non-glare off-white (`#f9f9f9`) to reduce fatigue, while the active workspace cards use pure White (`#ffffff`) to stand out.
- **Semantic Indicators (Validation & Alerts):**
  - **Red (`#C62828`):** Critical errors, missing mandatory values, or flagged problems.
  - **Green (`#2E7D32`):** Verified data, completed audits, or successful reviewed states.
  - **Yellow (`#FBC02D`):** Warning states, pending discrepancies, or unsaved drafts.
  - **Blue (`#0284C7`):** Versioning conflicts, historical discrepancies, or external database queries.
- **Accents:** Secondary branding utilizes a deep Botanical Green (`#2e6b30`), and a sharp Search Orange (`#D9480F`) is reserved exclusively for query highlighters and active search states.

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

### Rule 3: Single-Threaded Tkinter Event Loop
- **Non-blocking Operations:** Heavy tasks, image fetching, and database operations should occur in a background thread or be scheduled incrementally using `root.after()`.
- **Eager Error Capturing:** When scheduling deferred callbacks (e.g., `self.root.after`) inside exception handling blocks, capture the target exception message or traceback eagerly using default argument parameters (e.g., `lambda em=err_msg: ...`) rather than referencing free variables from the deleted exception scope to avoid silent `NameError` exceptions.

### Rule 4: Compact Form Serialization (Autosaves)
- **Use `.autosave.json`:** Temporary background sessions are serialized into the fast string JSON file format (`.autosave.json`). Ensure any custom UI state is serializable or properly decoupled from visual Tkinter widgets.
- **Edit Source, Not Artifacts:** If a file is a compiled build artifact, do not edit it directly. Trace the code back to its Python source under the `ui/` directory and recompile accordingly.

---

## 6. Template: User Intentions Behind UI Designs

*This section is dedicated to capturing user-specific UI layout guidelines and design goals. AI agents should reference this section to align with the core visual strategy requested by the owner.*

- **Design Philosophy:** Keep the interface clean, simple, and straightforward. Users are handling large collections of dry, textual botanical specimens. The UI should act as a silent, efficient assistant.
- **Color Accent Intention:** Do not over-saturate layouts. Use soft, non-glare off-whites on the main panel background to minimize visual fatigue. Reserved intense accent colors (Status Red, Search Orange) must be used sparingly to draw the user's eyes specifically to actionable items.
- **Symmetry and Alignment:** Maintain strict, consistent visual alignment. Use borders and background panel tones as the primary visual separators. Space forms cleanly and logically.
- **Space and Laptop Preservation:** Make tabs, lists, and tools collapsible or togglable. When users need more screen estate for visual inspection of specimens, the interface must let them hide auxiliary lists or panels without obstructing the core workflow.
