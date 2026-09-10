# Startup Window Review & Simplification Suggestions

After reviewing the `StartupDialog` codebase, I have identified several issues—particularly with features that are non-functional, buggy, or overly complicated. Below is a detailed report and a set of suggestions to simplify and improve the user experience.

---

## 1. Identified Issues & Broken Features

### A. The "Import Excel/CSV" Field Does Nothing
- **Issue:** The UI includes an "Import Excel/CSV (Optional Data Source)" field. However, when the user clicks "LAUNCH SYSTEM," the program completely ignores this field. The `finish()` method explicitly overwrites the selected import path with the main Database path.
- **Side Effect:** If a user selects an import file and then clicks the **Mobile Companion** button, a bug occurs where the mobile server attempts to launch using the *import* file instead of the main database, because the Mobile Companion launch bypasses the `finish()` method's overwrite logic.

### B. "Advanced Setup" is Buggy and Confusing
- **Config Overwrite Bug:** In the Advanced Setup, users are asked to select a "database config" before loading Books. However, when they return to the main screen and click "LAUNCH SYSTEM", the `finish()` method uses a hardcoded name-matching algorithm (e.g., checking if the filename contains the config name) and **completely overwrites** the config chosen in the Advanced Setup.
- **Crash Potential:** If a user clicks "Load Earlier Databases" in Advanced Setup *before* "Load Books", the application attempts to load the historical databases without a configuration set (`self.app.config`), which can lead to data parsing errors or a crash.
- **Architectural Flaw:** Loading heavy data (like Books or Historical DBs) asynchronously during the *startup* phase is fragile. It disables the launch buttons and forces the user to wait in a secondary dialog before the main application has even initialized.

### C. Layout Clutter
- The "+ Create New Database" button is squeezed into the section header of the Database field, making it easy to miss.
- The "Recent Projects" table uses an auto-scaling ellipsis algorithm for file paths that can be computationally heavy, and the column for "LAST MODIFIED" takes up horizontal space that could be used to show more of the file path.
- The window tries to adapt its layout (compact vs normal) based on resizing, which sometimes causes jarring font size changes.

---

## 2. Simplification Suggestions

### Recommendation 1: Remove "Import Excel/CSV" Entirely
Since this field literally does not function at startup and causes bugs with the Mobile Companion, it should be entirely removed from `StartupDialog`. Any data importing logic should be handled from inside the main application window (e.g., via a "File -> Import" menu) where the environment is fully initialized.

### Recommendation 2: Remove "Advanced Setup" from Startup
The Books and Historical DBs loading should not happen in the startup window.
- **Action:** Remove the "Advanced Setup" button and its corresponding popup dialog.
- **Alternative:** Move the "Load Books" and "Load Earlier Databases" functionality into the main UI window (perhaps under an "Advanced" or "Tools" tab). This ensures that the main database is fully loaded and a proper configuration is established *before* loading auxiliary data.

### Recommendation 3: Streamline the Layout
- **Database Selection:** Move the "+ Create New Database" button out of the tiny header and make it a prominent button next to or below the main Database selection field.
- **Recent Projects:** Simplify the list. Remove the "LAST MODIFIED" column so the full file path has more room to breathe.
- **Configs:** If database configurations (`DATABASE_CONFIGS`) are important to choose at startup, provide a simple, single dropdown on the main card (e.g., below the DB path) and disable the auto-guessing in `finish()`. Otherwise, let the auto-guessing do its job silently.

## Conclusion
The startup window currently acts as both a launcher and an advanced data-loading wizard, which creates conflicting states and bugs. By removing the non-functional Import field and deferring Advanced Setup to the main application, the startup window will become much cleaner, faster, and bug-free.