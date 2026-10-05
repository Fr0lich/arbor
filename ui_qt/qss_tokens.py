"""Design tokens from documentation/agent/AI_UI_GUIDE.md.

The .ui files embed all static styling as QSS. These constants exist so the
controllers can create dynamic widgets (form cards, problem checkboxes) that
match, and toggle state via dynamic properties, e.g.::

    edit.setProperty("problem", True)
    edit.style().unpolish(edit); edit.style().polish(edit)
"""

SURFACE = "#fbfaf8"
CARD = "#ffffff"
HEADER_ROW = "#f2f5f1"
CONTAINER = "#e9ece5"
TEXT = "#2c302e"
SUBTEXT = "#747878"
BORDER = "#747878"
HAIRLINE = "#c4c7c7"
GREEN = "#3a7d44"
RED = "#c93a40"
YELLOW = "#d9a036"
BLUE = "#4a7b9d"
SEARCH_ORANGE = "#d95c14"
BLACK = "#000000"

FONT_UI = "'Segoe UI', 'Inter', sans-serif"
FONT_MONO = "'Courier New', 'JetBrains Mono', monospace"


def repolish(widget) -> None:
    """Re-evaluate the stylesheet after changing a dynamic property."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
