# Palette's Journal

## 2025-08-03 - [Initial Setup]
**Learning:** Initialized Palette journal for arbor.
**Action:** Ready to track UX and accessibility learnings.

## 2025-08-03 - [Navigation Header Tooltips and Semantic Clarification]
**Learning:** The 'arbor' topbar utilized flat style `Nav.TButton` widgets without labels indicating shortcut keys or explicit actions, and included a confusing placeholder labeled 'FREE BUTTON'. In desktop environments where screen real-estate is optimized (such as laptop views), adding contextual tooltips directly via the application's built-in `self.add_tooltip` method dramatically improves feature discoverability and user onboarding without adding visual clutter to the navigation area.
**Action:** Always verify that navigation and control elements have a corresponding tooltip or shortcut indicator to assist screen-reader and hover users.
