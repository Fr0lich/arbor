with open("GEMINI_MASTER_PROMPT.md", "r") as f:
    text = f.read()

text = text.replace("### Phase 1: Data Architecture Expansion (`df_unvalidated`)", "### Phase 1: Data Architecture Expansion (`df_unvalidated`)\n**Goal & Intent:** Prepare the underlying data storage and state management systems so they can hold and persist the new 'Unvalidated Source' flags without breaking existing file formats. We are adding a new sheet/table that ties flags to specific ObjectIDs and fields.")
text = text.replace("### Phase 2: Unified REV+ERR Visual State & Tests", "### Phase 2: Unified REV+ERR Visual State & Tests\n**Goal & Intent:** Resolve the UI inconsistency across Desktop and Mobile by ensuring that objects which are both 'Reviewed' but still have unresolved 'Problems' clearly display a warning state, rather than a completely green 'OK' state.")
text = text.replace("### Phase 3: \"Unvalidated Source\" UI & Mobile Sync", "### Phase 3: \"Unvalidated Source\" UI & Mobile Sync\n**Goal & Intent:** Create the user interface for marking fields as unvalidated and capturing comments explaining why. Ensure these flags are smoothly synchronized between the Desktop app and the Mobile companion, including offline support via IndexedDB.")
text = text.replace("### Phase 4: Taxonomic Mass Update via GBIF (Desktop Only)", "### Phase 4: Taxonomic Mass Update via GBIF (Desktop Only)\n**Goal & Intent:** Provide a bulk-update mechanism for taxonomic data by querying the GBIF API. This will save curators significant time while ensuring that all original taxonomic data is preserved securely in the `Log` sheet for easy auditing and potential rollback.")
text = text.replace("### Phase 5: Expanded Filtering Options", "### Phase 5: Expanded Filtering Options\n**Goal & Intent:** Make the newly added data states actionable by allowing users to easily find objects that have 'Unvalidated' sources, are in the 'REV+ERR' state, or have historical taxonomic changes logged in the database.")
text = text.replace("### Phase 6: Final Verification", "### Phase 6: Final Verification\n**Goal & Intent:** Guarantee stability and correctness by running the full test suite and adhering to the project's quality standards before finalizing the implementation.")

with open("GEMINI_MASTER_PROMPT.md", "w") as f:
    f.write(text)
