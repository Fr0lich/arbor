## 2024-06-25 - Tooltips for Terse UI Buttons
**Learning:** Buttons with terse text labels (like "Source..." or "View: Gallery") can still benefit significantly from tooltips to clarify their specific function, especially when they act as menus or toggles, reducing user hesitation and improving discoverability.
**Action:** Always evaluate if short or ambiguous text buttons need a tooltip to fully explain their action, rather than only adding tooltips to icon-only buttons.
## $(date +%Y-%m-%d) - Native Input Touch Targets
**Learning:** Expanding touch targets (e.g., minimum 44x44px for mobile accessibility) by directly applying utility classes to a native `<input type="checkbox">` forces browsers to scale the checkmark disproportionately, causing visual regressions.
**Action:** Always wrap native inputs (like checkboxes or radio buttons) in a `<label>` element and apply the touch target size classes to the wrapper, rather than the input itself.
