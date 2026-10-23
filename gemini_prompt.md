# Gemini Prompt: Arbor GBIF Integration in Historical Resolver

You are an expert Python developer tasked with improving the GBIF integration in "Arbor", a Museum Object Visualizer desktop program built with Tkinter and Pandas.

## Context and Goal
Currently, the program allows users to search up objects, check for problems, and use a "Historical Database Conflict Resolver" to fix data using historical discrepancy suggestions. The current GBIF integration is a button hidden behind an advanced setting that only appears in the main taxonomy panel and only checks the current Genus/Species.

**The Goal:** Integrate GBIF directly into the Historical Discrepancy Resolver so it can utilize historical suggestions to find correct taxonomy data (Genus, Species, Family, Author) and present the results seamlessly as resolution options for the user.

## Requirements

### 1. Advanced Settings Updates (`ui/advanced_settings.py`)
Add two new toggles to the `ADVANCED_SETTINGS_SCHEMA` under the "Taxonomy Validation" group:
1.  **GBIF Resolver Combo Mode**: A toggle/choice. Default is "Best Match Only". Alternative is "Show All Matches".
    *   *Tooltip/Description*: Choose how multiple historical Genus/Species combinations are handled. "Best Match Only" (Pros: clean UI, fast; Cons: might miss biologically correct data if algorithm errs). "Show All Matches" (Pros: max transparency; Cons: can clutter the UI with options).
2.  **Auto-check GBIF in Resolver**: A toggle. Default is `False` (Disabled).
    *   *Tooltip/Description*: Automatically checks GBIF for all objects and auto-displays the results in the historical discrepancy window when it opens.

### 2. UI Additions in Historical Resolver (`ui/historical_resolver.py`)
*   **Check GBIF Button**: Add a "Check GBIF" button in the context header of the Historical Resolver window (near the issue count text).
    *   This button should *only* be visible if the global `enable_gbif` advanced setting is ON.
*   **Triggering the Check**: The check can be triggered manually by clicking the new button, or automatically on window initialization if "Auto-check GBIF in Resolver" is enabled.

### 3. Fallback & Combination Logic
When the GBIF check is triggered:
*   First, try the current `Genus` and `Species`.
*   If they are empty or invalid, **fallback to historical data**. Identify all historical suggestions for `Genus` and `Species` listed in the resolver's data structure.
*   If falling back, show a warning dialog to the user indicating that historical data combinations are being used for the search. **Crucial:** Suppress this warning if the "Auto-check GBIF in Resolver" setting is ON, to prevent spam.
*   Generate combinations of the historical Genus and Species suggestions (e.g., if Genus has "A", "B" and Species has "x", "y", check A x, A y, B x, B y).
*   Run `backend.gbif.check_gbif()` for these combinations in a background thread to prevent UI freezing.
*   Filter the results based on the "GBIF Resolver Combo Mode" setting (pick the top/best match, or keep all successful matches).

### 4. Displaying Results in the Resolver
*   For any valid GBIF match found, extract the `genus`, `species`, `family`, and `author`.
*   Inject these matches as new clickable suggestion buttons inside the respective field cards (Genus, Species, Family, Author) in the Historical Resolver UI.
*   **Styling**: The GBIF suggestion buttons must have a distinct, clear color to differentiate them from standard historical data. The source text on the button should say "Source: GBIF" and include reasoning (e.g., "Accepted Name", "Match Type: EXACT").
*   **Revealing Hidden Fields**: If GBIF returns data for a field (e.g., `Family`) that does *not* currently have a historical conflict (and is therefore hidden from the resolver view), you must reveal that field's card. Do not create a totally new, separate card implementation. Instead, utilize the existing logic of the "Show all fields" feature (the `show_all_var` and `reload_suggestions` methods) to properly instantiate and display the hidden card within the standard UI flow, then inject the GBIF button into it.

## Files to Edit
1.  `ui/advanced_settings.py`: Define the new settings in the schema.
2.  `ui/historical_resolver.py`: Implement the button, background fetching logic, combination generator, result injection into the cards, and the logic to reveal hidden cards using existing methods.
3.  `backend/gbif.py`: Review to ensure `check_gbif` can handle the burst of combination checks (it uses `requests`).

Please provide the implementation for these changes.