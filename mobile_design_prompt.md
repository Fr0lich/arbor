# System Prompt for Google Stitch: Arbor Mobile Web Companion Design

You are tasked with designing the UI for the "Mobile Web Companion" feature of Arbor ("Museum Object Visualizer"), a desktop application for reviewing and editing museum object databases. The desktop app starts a local server and users connect via their smartphones to walk around the collection, view items, and save edits.

Please generate a mobile-first, responsive web UI for this application. Ensure the design adheres strictly to the established Arbor visual identity and incorporates the necessary mobile workflows.

## 1. Visual Identity and Styling Rules

Your design must implement Arbor's specific aesthetic guidelines:

### A. Typography (Tri-Font Strategy)
- **Scholarly Serif (e.g., Lora, Georgia):** Use for primary page titles, main specimen headers, and botanical names.
- **Systematic Sans (e.g., Inter, Arial, Helvetica):** Use as the primary workhorse font for metadata forms, inputs, field labels, and general interactive UI text.
- **Technical Monospace (e.g., JetBrains Mono, Consolas):** Use for specimen IDs, coordinate strings, technical status indicators, and anywhere numbers need to align perfectly.

### B. Color Palette
- **Primary/Success Accent:** Vibrant Fern (`#3a7d44`).
- **Search/Active Accent:** Ember Orange (`#d95c14`). Use exclusively for query highlighters and active search states.
- **Backgrounds:** Use soft, non-glare off-whites (e.g., `#f3f3f3` vs `#ffffff`) for the main workspace to minimize visual fatigue.
- **Warning/Error:** Soft Yellow or Red tints for inputs; bold Red (e.g., solid 3px left border) for flagged problems or validation errors.

### C. Layout, Elevation, & Shapes
- **Depth & Layering:** Do not use fuzzy ambient shadows. Communicate depth purely through Tonal Layers (contrasting background colors like `#f3f3f3` against `#ffffff`).
- **Shapes:** Clean, structural elements with a soft `2px` (or `0.125rem`) border radius on buttons, fields, and badges to feel precise and professional.
- **Spacing:** Use a consistent rhythm with clean base unit padding.

## 2. Core Mobile Features & User Flow

The mobile web UI needs to support the following workflow and screens:

### A. Connection Screen
- A simple landing screen displayed when the user first opens the web app on their phone.
- Indicates successful connection to the desktop server.
- Optional: A prompt to scan a QR code if connecting for the first time or finding a specific session.

### B. Specimen List & Search
- A list view of museum objects.
- A prominent live search bar at the top (using the Ember Orange accent when active).
- Each list item should display the primary Scholarly Serif name, the Monospace ID, and brief Systematic Sans metadata.

### C. Object Detail & Edit View
This is the core workspace. Use a vertical, scrollable layout organized into distinct, collapsible cards. Do not clutter the screen; use standard mobile UX patterns to save space.

Include the following thematic cards:
1. **Taxonomy & Scientific Name (🧬):** Contains botanical names (Serif) and associated scientific fields.
2. **Collection & Specimen Metadata (📦):** Contains location, date, and collector info (Sans/Mono).
3. **Audit Notes & Descriptions (📝):** Contains multiline text areas for curator notes.

**Adaptive Validation Rules:**
- If an input field has a problem (e.g., missing data or historical discrepancy), dynamically style the input with a soft warning tint (Yellow/Red) and a solid 3px Red left-border accent bar. Label text should also shift to a warning color.

### D. Sticky Action Bar
- A persistent, sticky bar anchored to the bottom of the screen (Global Status & Action Bar).
- Contains a primary button (e.g., "Save Edits" or "Mark Reviewed" in Vibrant Fern) to submit changes back to the desktop server.
- Should remain visible at all times while scrolling the object details.

Please provide the HTML, CSS, and any necessary JavaScript (using standard web technologies or a framework of your choice, like React or Tailwind, as long as the visual rules are strictly followed) to implement this mobile UI.
