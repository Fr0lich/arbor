import os
import getpass
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import config
from config import sc, DATABASE_CONFIGS
from ui.scroll_helper import bind_mousewheel
import utils


# ============================================================================
# STRUCTURED BLUEPRINT CONTENT DICTIONARY
# Decouples user-facing explanations from Tkinter layout code.
# ============================================================================

SHEET_BLUEPRINT_INFO = {
    "reg": {
        "title": "🗂️ Sheet 1: Registration (Specimen Catalog)",
        "badge": " REQUIRED ",
        "badge_bg": "#3a7d44",
        "summary": "The main biological ledger. Each row represents one physical specimen in your collection.",
        "chips": [
            "ObjectID (Key)", "Genus", "Species", "Author", "Family",
            "Collector", "Date", "Locality", "Plant Part", "Online photo 1"
        ],
        "new_curator_bullets": (
            "🌱 For New Curators:\n"
            "  • This is where you enter specimens. Enter plant names, collectors, and localities.\n"
            "  • ObjectID: Your accession number (e.g. 1, 2, 1042, or O-2024-01).\n"
            "  • UID: Leave empty. Arbor assigns a unique 8-character fingerprint (e.g. 7921ac45) to protect records from mix-ups.\n"
            "  • Online Photos: Paste image links in 'Online photo 1–3' or link a local high-res photo folder."
        ),
        "curator_bullets": (
            "🏛️ For Experienced Curators:\n"
            "  • Primary Key: ObjectID (preserves leading zeros, expands scientific notation, strips Excel .0 floats).\n"
            "  • System GUID: UID (immutable 8-hex character identifier; used for mobile syncing and audit integrity).\n"
            "  • Core Taxonomy: Genus, Species, Author, Family, Higher Classification.\n"
            "  • Non-Destructive: You can add custom institutional columns; Arbor preserves them untouched."
        )
    },
    "obs": {
        "title": "🛡️ Sheet 2: Observation (Quality Workspace & Storage)",
        "badge": " AUTOMATIC ",
        "badge_bg": "#2d6a4f",
        "summary": "Stores quality problem flags and physical storage locations without modifying your catalog.",
        "chips": [
            "Genus_Problem", "Species_Problem", "Stored as", "Building",
            "Floor", "Cabinet", "Shelf", "Reviewed", "Images_Missing"
        ],
        "new_curator_bullets": (
            "🌱 For New Curators:\n"
            "  • You don't have to fill this out manually—Arbor manages this sheet for you!\n"
            "  • Problem Flags: Checking a problem box in the UI (e.g. Label Illegible) records it here.\n"
            "  • Reviewed Status: Clicking '✓ Mark as Reviewed' automatically stamps your name and review date here.\n"
            "  • Storage: Select cabinet and shelf dropdowns in Arbor to record physical locations."
        ),
        "curator_bullets": (
            "🏛️ For Experienced Curators:\n"
            "  • Relational Join: 1:1 join on ObjectID with Registration.\n"
            "  • 11 Standard Problem Booleans: Genus_Problem, Species_Problem, Family_Problem, Author_Problem,\n"
            "    PlantPart_Problem, Collector_Problem, Collection_Date_Problem, Collection_Place_Problem,\n"
            "    Box_Label_Problem, Images_Problem, Other_problem.\n"
            "  • Physical Storage: Building (Lid's hus, Økern), Floor, Cabinet, Shelf, Stored as, Loaned out.\n"
            "  • Review Metadata: Reviewed (bool), ReviewedAt (ISO timestamp), Images_Missing, Online_Images_Exist."
        )
    },
    "log": {
        "title": "📜 Sheet 3: Log (Audit Trail) & Transcription Notes",
        "badge": " SYSTEM ",
        "badge_bg": "#747878",
        "summary": "Silent change tracking for museum compliance, plus a scratchpad for uncertain notes.",
        "chips": [
            "Timestamp", "Action", "User", "ChangedFields",
            "ChangedValues", "Unvalidated_source"
        ],
        "new_curator_bullets": (
            "🌱 For New Curators:\n"
            "  • Your safety net: Whenever you edit a field, Arbor records what it was before so mistakes can be undone.\n"
            "  • Unvalidated_source Sheet: A place to write comments on illegible handwriting without corrupting clean fields."
        ),
        "curator_bullets": (
            "🏛️ For Experienced Curators:\n"
            "  • Institutional Provenance: Records Timestamp (ISO 8601), Action (EDIT, REVIEW), User, ObjectID,\n"
            "    ChangedFields, ChangedValues ('Old' -> 'New'), LocationChanged, and SourceFile.\n"
            "  • Unvalidated_source: 3-column table (ObjectID, Field_Name, Unvalidated_Comment) for raw OCR/draft annotations."
        )
    }
}


# ============================================================================
# CANONICAL STANDARD COLLECTION WORKBOOK GENERATOR
# ============================================================================

def create_standard_collection_file(file_path):
    """
    Generates a standard 4-sheet botanical collection workbook with 1 initial sample specimen.
    Derives canonical column definitions directly from config.py to ensure zero schema drift.
    """
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

    cfg = DATABASE_CONFIGS.get("Økonomisk Botanisk", {})
    ui_sections = cfg.get("ui_sections", {})

    # 1. Registration Columns
    reg_fields = ui_sections.get("registration", [])
    reg_columns = ["ObjectID", "Object Number"]
    for f in reg_fields:
        name = f.get("name")
        if name and name not in reg_columns:
            reg_columns.append(name)
    if "UID" not in reg_columns:
        reg_columns.append("UID")

    sample_reg = [{
        "ObjectID": "1",
        "Object Number": "1",
        "Variant": "",
        "UID": "7921ac45",
        "Genus": "Welwitschia",
        "Species": "mirabilis",
        "Author": "Hook.f.",
        "Family": "Welwitschiaceae",
        "Higher Classification": "48",
        "(N) Plant Part": "Stamme",
        "Plant Part": "Stem",
        "Collector": "Welwitsch, F.",
        "Innsammling Nr.": "104",
        "Collection Date": "1859",
        "Collection Place": "Cabo Negro, Angola",
        "Box Label": "Cabinet 4 / Shelf 2",
        "Observation": "Specimen mounted on wooden platform",
        "Conservation Status": "Good condition",
        "Comment": "Initial sample botanical record created by Arbor",
        "Other": "",
        "ProblemDescription": "",
        "Online photo 1": "https://www.unimus.no/photos/image/jpeg/O-V-OE-0001.jpg",
        "Online photo 2": "",
        "Online photo 3": ""
    }]
    df_reg = pd.DataFrame(sample_reg, columns=reg_columns)

    # 2. Observation Columns
    loc_fields = ui_sections.get("location", [])
    prob_fields = ui_sections.get("problems", [])

    obs_columns = ["ObjectID"]
    for p in prob_fields:
        name = p.get("name")
        if name and name not in obs_columns:
            obs_columns.append(name)

    for l in loc_fields:
        name = l.get("name")
        if name and name not in obs_columns:
            obs_columns.append(name)

    for sys_col in ["Images_Missing", "Reviewed", "ReviewedAt", "Online_Images_Exist"]:
        if sys_col not in obs_columns:
            obs_columns.append(sys_col)

    sample_obs = [{
        "ObjectID": "1",
        "Genus_Problem": False,
        "Species_Problem": False,
        "Family_Problem": False,
        "Author_Problem": False,
        "PlantPart_Problem": False,
        "Collector_Problem": False,
        "Collection_Date_Problem": False,
        "Collection_Place_Problem": False,
        "Box_Label_Problem": False,
        "Images_Problem": False,
        "Other_problem": False,
        "Stored as": "Mounted on wooden platform",
        "Floor": "1",
        "Cabinet": "4",
        "Shelf": "2",
        "Extra": "",
        "Building": "Lid's hus",
        "Loaned out": False,
        "Loaned out date": "",
        "Images_Missing": False,
        "Reviewed": False,
        "ReviewedAt": "",
        "Online_Images_Exist": True
    }]
    df_obs = pd.DataFrame(sample_obs, columns=obs_columns)

    # 3. Log
    log_columns = [
        "Timestamp", "Action", "Reviewed", "ObjectID", "ChangedFields", "ChangedValues",
        "ProblemsChanged", "ProblemsChangedValues", "LocationChanged", "LocationChangedValues",
        "User", "SourceFile", "OutputFile"
    ]
    sample_log = [{
        "Timestamp": datetime.now().isoformat(timespec="seconds"),
        "Action": "DATABASE_CREATED",
        "Reviewed": "",
        "ObjectID": "ALL",
        "ChangedFields": "Standard Botanical Collection Template",
        "ChangedValues": "Created initial collection with 1 sample record",
        "ProblemsChanged": "",
        "ProblemsChangedValues": "",
        "LocationChanged": "",
        "LocationChangedValues": "",
        "User": getpass.getuser(),
        "SourceFile": "",
        "OutputFile": os.path.basename(file_path)
    }]
    df_log = pd.DataFrame(sample_log, columns=log_columns)

    # 4. Unvalidated_source
    df_unval = pd.DataFrame(columns=["ObjectID", "Field_Name", "Unvalidated_Comment"])

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        df_reg.to_excel(writer, sheet_name="Registration", index=False)
        df_obs.to_excel(writer, sheet_name="Observation", index=False)
        df_log.to_excel(writer, sheet_name="Log", index=False)
        df_unval.to_excel(writer, sheet_name="Unvalidated_source", index=False)


# ============================================================================
# CREATE COLLECTION DIALOG COMPONENT
# ============================================================================

class CreateCollectionDialog:
    """
    Blueprint Preview & 1-Click Creator for New Botanical Collections.
    Provides clear, informative explanations of the 4-sheet architecture with
    interactive [?] detail expanders addressing both new and experienced curators.
    """
    C_BG          = "#fbfaf8"
    C_CARD        = "#ffffff"
    C_HEADER_BG   = "#fbfaf8"
    C_FOOTER_BG   = "#f2f5f1"
    C_SURFACE_LOW = "#f2f5f1"
    C_OUTLINE     = "#747878"
    C_OUTLINE_VAR = "#c4c7c7"
    C_ON_SURFACE  = "#2c302e"
    C_ON_VARIANT  = "#444748"
    C_PRIMARY     = "#000000"
    C_ON_PRIMARY  = "#ffffff"
    C_HOVER       = "#e9ece5"

    def __init__(self, parent, app=None, on_complete=None):
        self.parent = parent
        self.app = app
        self.on_complete = on_complete

        self._scale = getattr(config, "_detected_scale", 1.0)

        self.win = tk.Toplevel(parent)
        self.win.title("Create New Botanical Collection — Arbor")
        self.win.configure(bg=self.C_BG)
        self.win.transient(parent)
        self.win.grab_set()

        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        w = sc(min(700, max(480, screen_w - 40)))
        h = sc(min(680, max(450, screen_h - 70)))
        self.win.geometry(f"{w}x{h}")
        self.win.minsize(sc(460), sc(420))

        utils.center_and_fit_toplevel(self.win, w, h)

        self.save_path_var = tk.StringVar()
        default_dir = os.path.join(os.path.expanduser("~"), "Documents")
        if not os.path.isdir(default_dir):
            default_dir = os.getcwd()
        self.save_path_var.set(os.path.join(default_dir, "My_Botanical_Collection.xlsx"))

        # Details expansion state and widget map
        self._details_visible = {"reg": False, "obs": False, "log": False}
        self._detail_frames = {}
        self._detail_buttons = {}

        self._build_ui()

    def _build_ui(self):
        # ── FIXED HEADER ──────────────────────────────────────────────────
        header = tk.Frame(self.win, bg=self.C_HEADER_BG, padx=sc(16), pady=sc(10))
        header.pack(fill="x", side="top")

        tk.Label(
            header, text="arbor", font=("Courier New", sc(9), "bold"),
            bg=self.C_HEADER_BG, fg="#3a7d44"
        ).pack(anchor="w")

        tk.Label(
            header, text="Create New Botanical Collection",
            font=("Segoe UI", sc(15), "bold"), bg=self.C_HEADER_BG, fg=self.C_ON_SURFACE
        ).pack(anchor="w", pady=(sc(2), 0))

        tk.Label(
            header, text="Standard 4-Sheet Botanical Workbook (.xlsx) with built-in quality checks and audit log",
            font=("Segoe UI", sc(9)), bg=self.C_HEADER_BG, fg=self.C_ON_VARIANT
        ).pack(anchor="w")

        tk.Frame(self.win, bg=self.C_OUTLINE_VAR, height=1).pack(fill="x", side="top")

        # ── FIXED FOOTER ──────────────────────────────────────────────────
        tk.Frame(self.win, bg=self.C_OUTLINE_VAR, height=1).pack(fill="x", side="bottom")

        footer = tk.Frame(self.win, bg=self.C_FOOTER_BG, padx=sc(16), pady=sc(10))
        footer.pack(fill="x", side="bottom")

        cancel_btn = tk.Button(
            footer, text="Cancel", font=("Segoe UI", sc(9.5)),
            bg=self.C_CARD, fg=self.C_ON_SURFACE, relief="flat", bd=0,
            padx=sc(14), pady=sc(6), cursor="hand2",
            highlightthickness=1, highlightbackground=self.C_OUTLINE,
            command=self.win.destroy
        )
        cancel_btn.pack(side="left")

        create_btn = tk.Button(
            footer, text="✓ Create & Launch Collection (Recommended)",
            font=("Segoe UI", sc(10), "bold"),
            bg=self.C_PRIMARY, fg=self.C_ON_PRIMARY, relief="flat", bd=0,
            padx=sc(18), pady=sc(7), cursor="hand2",
            command=self._on_create_standard
        )
        create_btn.pack(side="right")
        create_btn.bind("<Enter>", lambda e: create_btn.config(bg="#333333"))
        create_btn.bind("<Leave>", lambda e: create_btn.config(bg=self.C_PRIMARY))

        # ── SCROLLABLE BODY (Laptop Friendly) ─────────────────────────────
        body_container = tk.Frame(self.win, bg=self.C_BG)
        body_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(body_container, bg=self.C_BG, highlightthickness=0)
        self.canvas = canvas
        sb = ttk.Scrollbar(body_container, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas, bg=self.C_BG, padx=sc(16), pady=sc(12))
        self.scrollable_frame = scroll_content
        self.scroll_content = scroll_content

        inner_id = canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)

        def _on_inner_cfg(e):
            if canvas.winfo_exists():
                canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_cfg(e):
            if canvas.winfo_exists():
                canvas.itemconfig(inner_id, width=e.width)

        scroll_content.bind("<Configure>", _on_inner_cfg)
        canvas.bind("<Configure>", _on_canvas_cfg)

        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Cross-platform non-destructive mousewheel binding
        bind_mousewheel(self.canvas, self.scrollable_frame)
        tag = f"ScrollTag_{id(self.canvas)}"
        if tag not in self.canvas.bindtags():
            self.canvas.bindtags((tag,) + tuple(self.canvas.bindtags()))

        # Build sheet cards from structured dictionary
        for key in ["reg", "obs", "log"]:
            self._build_sheet_card(scroll_content, key, SHEET_BLUEPRINT_INFO[key])

        self._build_destination_section(scroll_content)
        self._build_wizard_callout(scroll_content)

    def _build_sheet_card(self, parent, key, info):
        card = tk.Frame(parent, bg=self.C_CARD, highlightthickness=1, highlightbackground=self.C_OUTLINE_VAR, padx=sc(14), pady=sc(10))
        card.pack(fill="x", pady=(0, sc(10)))

        # Header row
        hdr = tk.Frame(card, bg=self.C_CARD)
        hdr.pack(fill="x")

        tk.Label(hdr, text=info["title"], font=("Segoe UI", sc(10.5), "bold"), bg=self.C_CARD, fg=self.C_ON_SURFACE).pack(side="left")

        badge = tk.Label(hdr, text=info["badge"], font=("Courier New", sc(8), "bold"), bg=info["badge_bg"], fg="#ffffff", padx=4, pady=1)
        badge.pack(side="left", padx=sc(8))

        btn = tk.Button(
            hdr, text="[?] Details", font=("Segoe UI", sc(8.5), "bold"),
            bg=self.C_SURFACE_LOW, fg=self.C_ON_SURFACE, relief="flat", bd=0,
            padx=sc(8), pady=sc(2), cursor="hand2",
            highlightthickness=1, highlightbackground=self.C_OUTLINE,
            command=lambda k=key: self._toggle_details(k)
        )
        btn.pack(side="right")
        self._detail_buttons[key] = btn

        # Summary
        tk.Label(
            card, text=info["summary"],
            font=("Segoe UI", sc(9)), bg=self.C_CARD, fg=self.C_ON_VARIANT, anchor="w"
        ).pack(fill="x", pady=(sc(2), sc(4)))

        # Field Chips
        chips_frame = tk.Frame(card, bg=self.C_CARD)
        chips_frame.pack(fill="x", pady=(0, sc(4)))
        for chip in info["chips"]:
            tk.Label(chips_frame, text=f" {chip} ", font=("Segoe UI", sc(8)), bg=self.C_SURFACE_LOW, fg=self.C_ON_SURFACE, padx=3, pady=1).pack(side="left", padx=(0, 4), pady=2)

        # Expandable Detail Frame
        detail_frame = tk.Frame(card, bg=self.C_SURFACE_LOW, padx=sc(12), pady=sc(8), highlightthickness=1, highlightbackground=self.C_OUTLINE_VAR)
        self._detail_frames[key] = detail_frame

        tk.Label(
            detail_frame, text=info["new_curator_bullets"],
            font=("Segoe UI", sc(8.5)), bg=self.C_SURFACE_LOW, fg=self.C_ON_SURFACE, justify="left", anchor="w"
        ).pack(fill="x", pady=(0, sc(6)))

        tk.Label(
            detail_frame, text=info["curator_bullets"],
            font=("Segoe UI", sc(8.5)), bg=self.C_SURFACE_LOW, fg=self.C_ON_VARIANT, justify="left", anchor="w"
        ).pack(fill="x")

    def _build_destination_section(self, parent):
        dest_card = tk.Frame(parent, bg=self.C_CARD, highlightthickness=1, highlightbackground=self.C_OUTLINE_VAR, padx=sc(14), pady=sc(10))
        dest_card.pack(fill="x", pady=(0, sc(10)))

        tk.Label(
            dest_card, text="Save New Collection File As:",
            font=("Segoe UI", sc(9.5), "bold"), bg=self.C_CARD, fg=self.C_ON_SURFACE
        ).pack(anchor="w", pady=(0, sc(4)))

        row = tk.Frame(dest_card, bg=self.C_CARD)
        row.pack(fill="x")

        entry = tk.Entry(
            row, textvariable=self.save_path_var,
            bg=self.C_SURFACE_LOW, fg=self.C_ON_SURFACE,
            font=("Courier New", sc(9.5)), relief="flat",
            highlightthickness=1, highlightbackground=self.C_OUTLINE
        )
        entry.pack(side="left", fill="x", expand=True, ipady=sc(5))

        browse_btn = tk.Button(
            row, text="Browse...", font=("Segoe UI", sc(9)),
            bg=self.C_SURFACE_LOW, fg=self.C_ON_SURFACE, relief="flat", bd=0,
            padx=sc(12), pady=sc(5), cursor="hand2",
            highlightthickness=1, highlightbackground=self.C_OUTLINE,
            command=self._on_browse_dest
        )
        browse_btn.pack(side="right", padx=(sc(6), 0))

    def _build_wizard_callout(self, parent):
        callout = tk.Frame(parent, bg=self.C_SURFACE_LOW, padx=sc(14), pady=sc(10), highlightthickness=1, highlightbackground=self.C_OUTLINE_VAR)
        callout.pack(fill="x")

        tk.Label(
            callout, text="Need custom fields, categories, or specialized quality flags?",
            font=("Segoe UI", sc(9)), bg=self.C_SURFACE_LOW, fg=self.C_ON_VARIANT
        ).pack(side="left")

        wiz_btn = tk.Button(
            callout, text="⚙ Customize in 6-Step Wizard...",
            font=("Segoe UI", sc(9), "bold"), bg=self.C_CARD, fg=self.C_ON_SURFACE,
            relief="flat", bd=0, padx=sc(10), pady=sc(3), cursor="hand2",
            highlightthickness=1, highlightbackground=self.C_OUTLINE,
            command=self._on_launch_wizard
        )
        wiz_btn.pack(side="right")
        wiz_btn.bind("<Enter>", lambda e: wiz_btn.config(bg=self.C_HOVER))
        wiz_btn.bind("<Leave>", lambda e: wiz_btn.config(bg=self.C_CARD))

    def _toggle_details(self, key):
        if key in self._detail_frames and key in self._detail_buttons:
            frame = self._detail_frames[key]
            btn = self._detail_buttons[key]
            is_vis = self._details_visible[key]
            if is_vis:
                frame.pack_forget()
                btn.config(text="[?] Details", bg=self.C_SURFACE_LOW)
                self._details_visible[key] = False
            else:
                frame.pack(fill="x", pady=(sc(8), 0))
                btn.config(text="[-] Close", bg="#e8f5e9")
                self._details_visible[key] = True

    def _on_browse_dest(self):
        initial = os.path.dirname(self.save_path_var.get())
        path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Choose Destination for New Collection File",
            initialdir=initial,
            initialfile="My_Botanical_Collection.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")]
        )
        if path:
            self.save_path_var.set(path)

    def _on_create_standard(self):
        target_path = self.save_path_var.get().strip()
        if not target_path:
            messagebox.showerror("Error", "Please specify a destination file path.", parent=self.win)
            return

        try:
            create_standard_collection_file(target_path)
            self.win.destroy()
            if self.on_complete:
                self.on_complete(target_path, "Økonomisk Botanisk")
        except Exception as e:
            messagebox.showerror("Creation Failed", f"Could not create collection workbook:\n{e}", parent=self.win)

    def _on_launch_wizard(self):
        self.win.destroy()
        from ui.new_database_wizard import NewDatabaseWizard
        NewDatabaseWizard(self.parent, self.app, self.on_complete)
