# Palette's Journal

## 2025-08-03 - [Initial Setup]
**Learning:** Initialized Palette journal for arbor.
**Action:** Ready to track UX and accessibility learnings.

## 2025-08-03 - [Navigation Header Tooltips and Semantic Clarification]
**Learning:** The 'arbor' topbar utilized flat style `Nav.TButton` widgets without labels indicating shortcut keys or explicit actions, and included a confusing placeholder labeled 'FREE BUTTON'. In desktop environments where screen real-estate is optimized (such as laptop views), adding contextual tooltips directly via the application's built-in `self.add_tooltip` method dramatically improves feature discoverability and user onboarding without adding visual clutter to the navigation area.
**Action:** Always verify that navigation and control elements have a corresponding tooltip or shortcut indicator to assist screen-reader and hover users.

## 2025-08-03 - [Structured Cards and Auto-Advance Workflow Enhancements]
**Learning:** Dividing large, flat metadata lists into themed, visually distinct card containers with icons improves visual grouping, layout structure, and cognitive scanning for audit operators. Combining this with an "Auto-next after review" option in the sticky action bar makes record processing extremely fast and fluid by automating navigation between items upon successful mark.
**Action:** Implement scrollable canvas views for card sections with distinct header icons/typography and automatic card-level visibility toggles in compact or Focus views.

## 2024-05-18 - [Delayed Tooltips over Instant Tooltips]
**Learning:** Instant tooltips without delays cause severe flickering and visual noise when hovering across dense toolbars or status icons, degrading the desktop application experience. Unstyled, system-default tooltips also break visual immersion, especially in dark mode.
**Action:** Always implement a ~500ms delay for tooltips and ensure they adapt to the application's theme (light/dark mode) using standard UI background and border colors.
