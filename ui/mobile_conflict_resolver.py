import tkinter as tk
from tkinter import ttk
from config import sc
from ui.historical_resolver import FONT_UI, FONT_UI_BOLD, FONT_UI_LG, FONT_UI_XL, FONT_MONO, FONT_MONO_SM, COLORS, init_fonts


class MobileConflictResolverWindow:
    def __init__(self, main_app, oid, conflicts, apply_callback):
        """
        conflicts: list of dicts:
        [
            {
                "field": "species",
                "desktop_value": "Oak",
                "mobile_value": "Pine"
            }, ...
        ]
        """
        init_fonts()
        self.main_app = main_app
        self.oid = oid
        self.conflicts = conflicts
        self.apply_callback = apply_callback

        self.win = tk.Toplevel(main_app.root)
        self.win.title("Mobile Conflict Resolver")
        self.win.configure(bg=COLORS["bg"])

        import utils
        utils.center_and_fit_toplevel(self.win, sc(800), sc(600))

        # field -> tk.StringVar (value will be 'desktop' or 'mobile')
        self.selections = {}
        for c in conflicts:
            self.selections[c["field"]] = tk.StringVar(
                value="desktop")  # default to desktop winning

        self.build_ui()

    def build_ui(self):
        # Header
        header = tk.Frame(self.win, bg=COLORS["surface"], height=sc(48))
        header.pack(fill="x", side="top")
        tk.Frame(header, bg=COLORS["border"], height=sc(1)).pack(
            fill="x", side="bottom")

        tk.Label(header, text="MOBILE CONFLICT RESOLVER", font=FONT_UI_LG,
                 fg=COLORS["primary"], bg=COLORS["surface"]).pack(side="left", padx=sc(16), pady=sc(12))

        # Main content area
        main_area = tk.Frame(self.win, bg=COLORS["bg"])
        main_area.pack(fill="both", expand=True)

        # Context Header
        ctx_header = tk.Frame(main_area, bg=COLORS["surface"])
        ctx_header.pack(fill="x")
        tk.Frame(ctx_header, bg=COLORS["border"], height=sc(1)).pack(
            side="bottom", fill="x")

        tk.Label(ctx_header, text=f"CONFLICTS FOUND: {len(self.conflicts)}", font=FONT_UI_XL, fg=COLORS["error"], bg=COLORS["surface"]).pack(
            anchor="w", padx=sc(24), pady=(sc(16), sc(4)))
        tk.Label(ctx_header, text="You have unsaved changes on Desktop that were just modified via Mobile.",
                 font=FONT_UI, fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", padx=sc(24), pady=(0, sc(16)))

        # Scrollable Canvas
        self.canvas = tk.Canvas(
            main_area, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            main_area, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=COLORS["bg"])

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox(
                "all")) if e.widget == self.scrollable_frame else None
        )
        canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda e,
                         cw=canvas_window: self.canvas.itemconfig(cw, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Bind mousewheel
        def _on_mousewheel(event):
            try:
                if self.canvas.winfo_exists():
                    self.canvas.yview_scroll(
                        int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Cards
        for conflict in self.conflicts:
            self.create_card(conflict)

        # Footer
        footer = tk.Frame(self.win, bg=COLORS["surface_dim"], height=sc(48))
        footer.pack(fill="x", side="bottom")
        tk.Frame(footer, bg=COLORS["border"],
                 height=sc(1)).pack(side="top", fill="x")

        btn_apply = tk.Button(footer, text="APPLY SELECTIONS", font=FONT_UI_BOLD, fg=COLORS["on_success"], bg=COLORS["success"], relief="flat", bd=0, padx=sc(
            16), pady=sc(8), command=self.apply, cursor="hand2")
        btn_apply.pack(side="right", padx=sc(16), pady=sc(6))

        btn_close = tk.Button(footer, text="CANCEL", font=FONT_UI_BOLD, fg=COLORS["text"], bg=COLORS["surface"], relief="solid", bd=1, padx=sc(
            16), pady=sc(8), command=self.win.destroy, cursor="hand2")
        btn_close.pack(side="right", padx=sc(8), pady=sc(6))

        def _cleanup(event=None):
            if event and event.widget != self.win:
                return
            try:
                self.canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass
        self.win.bind("<Destroy>", _cleanup)

    def create_card(self, conflict):
        field = conflict["field"]
        desktop_val = conflict["desktop_value"]
        mobile_val = conflict["mobile_value"]

        card = tk.Frame(self.scrollable_frame,
                        bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1)
        card.pack(fill="x", padx=sc(24), pady=(sc(24), 0))

        header = tk.Frame(card, bg=COLORS["error"])
        header.pack(fill="x")
        tk.Label(header, text=f"FIELD: {field.upper()}", font=FONT_UI_BOLD, fg=COLORS["on_error"], bg=COLORS["error"]).pack(
            side="left", padx=sc(16), pady=sc(10))
        tk.Label(header, text="CFCT", font=FONT_MONO_SM, fg=COLORS["on_error"], bg=COLORS["error"]).pack(
            side="right", padx=sc(16), pady=sc(10))

        content = tk.Frame(card, bg=COLORS["surface"])
        content.pack(fill="x", padx=sc(20), pady=sc(20))

        # Options
        var = self.selections[field]

        # Desktop Card
        desk_frame = tk.Frame(
            content, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1, cursor="hand2")
        desk_frame.pack(fill="x", pady=(0, sc(8)))

        desk_rb = tk.Radiobutton(desk_frame, text="Keep Desktop Value (Unsaved)", variable=var,
                                 value="desktop", font=FONT_UI_BOLD, bg=COLORS["surface"], fg=COLORS["text"], cursor="hand2")
        desk_rb.pack(anchor="w", padx=sc(8), pady=(sc(8), 0))

        tk.Label(desk_frame, text=desktop_val if desktop_val else "[BLANK]", font=FONT_MONO, fg=COLORS["text"]
                 if desktop_val else COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", padx=sc(28), pady=(0, sc(8)))

        # Mobile Card
        mob_frame = tk.Frame(
            content, bg=COLORS["surface"], highlightbackground=COLORS["border"], highlightthickness=1, cursor="hand2")
        mob_frame.pack(fill="x", pady=(0, sc(8)))

        mob_rb = tk.Radiobutton(mob_frame, text="Use Mobile Value", variable=var, value="mobile",
                                font=FONT_UI_BOLD, bg=COLORS["surface"], fg=COLORS["text"], cursor="hand2")
        mob_rb.pack(anchor="w", padx=sc(8), pady=(sc(8), 0))

        tk.Label(mob_frame, text=mobile_val if mobile_val else "[BLANK]", font=FONT_MONO, fg=COLORS["text"]
                 if mobile_val else COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", padx=sc(28), pady=(0, sc(8)))

        def _sel_desktop(e): var.set("desktop")
        def _sel_mobile(e): var.set("mobile")

        desk_frame.bind("<Button-1>", _sel_desktop)
        for w in desk_frame.winfo_children():
            w.bind("<Button-1>", _sel_desktop)

        mob_frame.bind("<Button-1>", _sel_mobile)
        for w in mob_frame.winfo_children():
            w.bind("<Button-1>", _sel_mobile)

    def apply(self):
        final_choices = {}
        for c in self.conflicts:
            field = c["field"]
            choice = self.selections[field].get()
            final_choices[field] = {
                "choice": choice,
                "desktop_value": c["desktop_value"],
                "mobile_value": c["mobile_value"]
            }

        self.apply_callback(self.oid, final_choices)
        self.win.destroy()
