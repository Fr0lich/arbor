import tkinter as tk

class LayoutStateManager:
    """
    A dedicated class for handling UI geometry/visibility states (pack/grid/forget)
    safely using winfo_exists().
    """
    def __init__(self, main_window):
        self.main_window = main_window

    def update_reg_fields_visibility(self, focus_mode_active, active_problems, is_edit_mode=False):
        """
        Updates the visibility of the accordion cards/fields based on focus mode and problems.
        Replaces tangled logic inside main_window.load_object.
        """
        main = self.main_window

        if not hasattr(main, "card_frames") or not main.card_frames:
            return

        for c_id, card_data in main.card_frames.items():
            card_frame = card_data["frame"]
            if not card_frame.winfo_exists():
                continue

            card_has_active_fields = False
            for fname in card_data["fields"]:
                if fname not in main.reg_row_frames:
                    continue

                row_frame = main.reg_row_frames[fname]
                if not row_frame.winfo_exists():
                    continue

                if focus_mode_active:
                    # In focus mode, only show if there's an active problem mapped to this field
                    if fname in active_problems:
                        row_frame.pack(fill="x", pady=2)
                        card_has_active_fields = True
                    else:
                        row_frame.pack_forget()
                else:
                    # Normal mode, show all fields
                    row_frame.pack(fill="x", pady=2)
                    card_has_active_fields = True

            # Toggle the entire card's visibility
            if focus_mode_active and not card_has_active_fields:
                card_frame.pack_forget()
            else:
                card_frame.pack(fill="x", padx=10, pady=6)

            # Automatically expand the accordion body if we are in focus mode and have problems
            if focus_mode_active and card_has_active_fields:
                body = card_data["body"]
                toggle_lbl = card_data["toggle_lbl"]
                if body.winfo_exists() and toggle_lbl.winfo_exists():
                    body.pack(fill="x")
                    toggle_lbl.config(text="▼")
