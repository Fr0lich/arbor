# Feature Catalog

This document catalogues all current features implemented in the **arbor** project so that they can be easily tracked, referenced, and restored if disabled.

---

## 1. Core Workflow Features
*   **Excel Sync & Repository Auto-Backup**: Keeps data loaded into local memory from Excel files, autosaves changes every 2 minutes (.autosave.json), and tracks file modifications.
*   **Checked/Reviewed Statusing**: Allows users to mark records as  Reviewed. Displays a checkbox column in the object list and records review times.
*   **High-DPI Compatibility**: Automatically checks system scaling settings upon launch to adapt font sizes and dimensions dynamically for clear laptop viewports.

---

## 2. Advanced Interactive Subsystems
*   **Doubt/Problem Highlighting**: If a checklist problem field is checked (e.g. Species_Problem), the corresponding registration field (e.g., Species entry) is visually highlighted in yellow to direct attention to discrepant or incomplete data.
*   **Historical Conflict Resolution**: Detects schema mismatch errors between older local save files and the active database schema, prompting the user with an interactive resolver.
*   **Interactive Tutorial Manager**: An onboarding component that overlays visual guide dialogs instructing the user how to configure, browse, edit, and search objects.
*   **Taxonomy Accordions/Tabs**: Group input controls under logical taxonomy dividers (e.g. taxonomy, collection meta, storage location, admin).
*   **Virtual Keyboard Bindings**: Binds shortcuts to space, arrow keys, and control modifiers for rapid editing without requiring a mouse.
*   **Image viewer canvas**: Implements gallery layouts, rotation angles, dynamic URL patterns, and image zoom configurations.
*   **Bulk Editor Window**: Allows users to search, query, and bulk update registration or location fields across multiple selected objects at once.
