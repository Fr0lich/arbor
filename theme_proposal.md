## Visual Theme Proposal: Botanical Sage & Deep Forest Night

### Concept & General UI
The current UI uses a stark, utilitarian palette (`#f9f9f9` and pure white `#ffffff` with black `#000000` text). The proposed theme introduces a softer, more organic aesthetic that aligns with Arbor's botanical and archival focus. It reduces eye strain while maintaining a high-contrast, professional, academic feel. The shapes should remain structural with soft 4px (`0.25rem`) corner radii for buttons, bringing a slightly more modern "card" feel without being overly playful.

### Background Colors
**Light Mode (Botanical Sage):**
*   **App Background / Main Canvas:** Warm Alabaster (`#fbfaf8`) instead of the cold `#f9f9f9`.
*   **Workspace Cards / Form Backgrounds:** Pure White (`#ffffff`) for crisp data entry.
*   **Sidebar / Drawer Background:** Soft Sage (`#f2f5f1`) to visually separate navigation from the work area.
*   **Header / Topbar:** Muted Olive (`#e9ece5`) to ground the application.
*   **Text / On-Surface:** Charcoal (`#2c302e`) rather than pure black `#000000` to reduce harsh contrast.

**Dark Mode (Deep Forest Night):**
*   **App Background / Main Canvas:** Deep Pine (`#181c19`) replacing the stark `#1e1e2e`.
*   **Workspace Cards / Form Backgrounds:** Rich Forest (`#212622`).
*   **Sidebar / Drawer Background:** Dark Moss (`#1e221f`).
*   **Header / Topbar:** Obsidian Green (`#141715`).
*   **Text / On-Surface:** Soft Pearl (`#e8ebe9`) instead of pure white to avoid blooming on screens.

### Icon Colors & Accents
*   **Primary Action Accents:** Vibrant Fern (`#3a7d44`). Replaces the current deep green (`#2e6b30`) with a slightly more luminous green for better visibility and modern feel.
*   **Search & Highlight Accent:** Ember Orange (`#d95c14`), slightly softened from `#D9480F` to harmonize with the sage backgrounds.
*   **Icons (Inactive):** Slate Grey (`#757d77` in light mode, `#8b948d` in dark mode).
*   **Icons (Hover/Active):** Vibrant Fern (`#3a7d44`) or Charcoal/Soft Pearl depending on the surface.
*   **Status Indicators:**
    *   Error/Problem: Brick Red (`#c93a40`)
    *   Warning: Mustard Yellow (`#d9a036`)
    *   Info/Historical: Slate Blue (`#4a7b9d`)
    *   Success/Reviewed: Vibrant Fern (`#3a7d44`)

### What Needs to be Changed in the Codebase
To implement this theme, the following areas in the codebase will need updates:

1.  **`AI_UI_GUIDE.md`**:
    *   Update the `colors` YAML dictionary to reflect the new palettes (e.g., changing `background`, `surface`, `secondary`, and semantic statuses like `status-red`).
    *   Update the color descriptions under the "Color Palette" section to match Botanical Sage/Deep Forest Night instead of standard black/white.

2.  **`config.py`**:
    *   Update `RAIL_THEME` and `DRAWER_THEME` background/border colors to use the Sage/Moss tones.
    *   Update `BANNER_THEME` configurations to use the new semantic Brick/Mustard/Fern/Slate colors.

3.  **`ui/layout_settings.py`**:
    *   In the `apply_theme` method, completely overhaul the hardcoded hex codes for both `dark_mode_active` and the light mode fallback.
    *   Change values for `bg_color`, `fg_color`, `field_bg`, `select_bg`, `border_color`, `statusbar_bg`, etc.
    *   Update the Tkinter `ttk.Style` configurations mapped in `apply_theme` (e.g., `style.configure(".", background=...)`, `style.configure("Primary.TButton", ...)`).
    *   Update the `status_badge_colors` dictionary.

4.  **`ui/main_window.py`**:
    *   Update hardcoded UI colors in elements constructed outside the main `ttk.Style`, such as custom Canvases, the `_status_bar_frame`, the `nav_bar` header, and the `drawer_overlay`.
    *   Update the specific Hex codes used for the problem borders (`#ba1a1a` -> `#c93a40`) and hover states (`#e8e8e8`).

5.  **Individual UI Components (`ui/add_objects.py`, `ui/image_toolbar.py`, `ui/new_database_wizard.py`, `ui/location_panel.py`, `ui/recent_activity_dialog.py`)**:
    *   Update the local `COLORS_LIGHT` and `COLORS_DARK` dictionaries declared at the top of these files to match the new palettes.

6.  **`ui/widgets.py` & other UI modules (`ui/group_editor.py`, `ui/unified_settings.py`, `ui/database_ops.py`)**:
    *   Update hover and active background hex codes in custom widget definitions to match the new hover aesthetics.
