with open("ui/widgets.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "def _populate_card_widget" in line:
        pop_idx = i
        break

# Address the bug reported in the review
# The review said: "in the `if reviewed:` branch, it completely forgot to assign a value to `accent_color`."
# But looking at the file:
#         if reviewed:
#             accent_color = "#4CAF50" if is_dark else "#2E7D32"  # green
#             badge_label, badge_bg, badge_fg = "OK",      "#2E7D32", "#ffffff"
# Wait, it IS there. Let me re-read the review carefully.
# "If a user scrolls to a card that has been `reviewed`, the application will throw an `UnboundLocalError: local variable 'accent_color' referenced before assignment`"
# Ah! I see! In my earlier version, I didn't have it. In my latest patch, maybe I did include it, but the reviewer noticed the old patch? Or maybe the review is right and I'm missing something else.
# Wait, `accent_color` is used before assignment?
# Let's read lines 1035-1055.
# Yes, `accent_color` is assigned.
# The reviewer also said:
# "By decoupling the widget creation, the base background colors (`card_bg`, `canvas_bg`) are only applied once during `_build_empty_card_widget`. If the application supports dynamically toggling dark mode without a restart or full UI rebuild, recycled cards will retain their original theme colors because `_populate_card_widget` does not re-apply the base backgrounds to the recycled frames."

for i in range(pop_idx, len(lines)):
    if 'widgets["accent_strip"].configure(bg=accent_color)' in lines[i]:
        insert_idx = i
        break

indent = len(lines[insert_idx]) - len(lines[insert_idx].lstrip())
sp = " " * indent

theme_patch = f"""{sp}widgets["outer_frame"].configure(bg=canvas_bg)
{sp}widgets["card_body"].configure(bg=card_bg)
{sp}widgets["row1"].configure(bg=card_bg)
{sp}widgets["row2"].configure(bg=card_bg)
{sp}widgets["row3"].configure(bg=card_bg)
{sp}widgets["cb_lbl"].configure(bg=card_bg)
{sp}widgets["tax_lbl"].configure(bg=card_bg)
{sp}widgets["fam_lbl"].configure(bg=card_bg)
{sp}widgets["sep_lbl"].configure(bg=card_bg)
{sp}widgets["id_lbl"].configure(bg=card_bg)
{sp}widgets["photo_lbl"].configure(bg=card_bg)
{sp}widgets["loc_lbl"].configure(bg=card_bg)
"""

lines.insert(insert_idx, theme_patch)

with open("ui/widgets.py", "w") as f:
    f.writelines(lines)
