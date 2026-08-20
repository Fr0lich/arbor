import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import json
import logging
from config import sc

logger = logging.getLogger("arbor")

class GBIFMixin:
    def __init__(self):
        super().__init__()
        self._gbif_cache = {}
        self._gbif_active_request = None
        self._gbif_listbox = None
        self._gbif_debounce_timer = None

    def gbif_query_match(self, name):
        """Query GBIF for a species name match (for checking modern name)"""
        url = "https://api.gbif.org/v1/species/match"
        params = {"name": name, "strict": "false"}
        try:
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except requests.RequestException as e:
            logger.error(f"GBIF API Error: {e}")
        return None

    def gbif_query_suggest(self, query):
        """Query GBIF for taxonomy suggestions"""
        if query in self._gbif_cache:
            return self._gbif_cache[query]

        url = "https://api.gbif.org/v1/species/suggest"
        params = {"q": query, "datasetKey": "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"} # GBIF Backbone Taxonomy
        try:
            resp = requests.get(url, params=params, timeout=3)
            if resp.status_code == 200:
                results = resp.json()
                # filter to just plants or general taxa, formatting as strings
                suggestions = []
                for r in results:
                    rank = r.get("rank", "").lower()
                    if rank in ("genus", "species", "family"):
                        suggestions.append(r)

                self._gbif_cache[query] = suggestions
                return suggestions
        except requests.RequestException as e:
            logger.error(f"GBIF Suggest Error: {e}")

        return []

    def check_modern_name_ui(self):
        """Called by UI button to check and update taxonomy"""
        # Ensure we have object ID
        oid = getattr(self.app, "current_object_id", None)
        if not oid:
            return

        genus_var = self.reg_vars.get("Genus")
        species_var = self.reg_vars.get("Species")
        if not genus_var or not species_var:
            return

        genus = genus_var.get().strip()
        species = species_var.get().strip()

        if not genus and not species:
            messagebox.showinfo("GBIF Check", "Please enter a Genus or Species first.", parent=self.root)
            return

        search_term = genus
        if species:
            search_term += f" {species}"

        # Run in background to not block UI
        def worker():
            res = self.gbif_query_match(search_term)
            if res:
                self.root.after(0, lambda: self._process_gbif_match_result(res, genus, species, oid))
            else:
                self.root.after(0, lambda: messagebox.showinfo("GBIF Check", "Network error or GBIF API unavailable.", parent=self.root))

        threading.Thread(target=worker, daemon=True).start()

    def _process_gbif_match_result(self, res, old_genus, old_species, oid):
        status = res.get("status")
        match_type = res.get("matchType")

        if match_type == "NONE":
            messagebox.showinfo("GBIF Check", "No match found for this taxonomy.", parent=self.root)
            return

        if status == "ACCEPTED":
            messagebox.showinfo("GBIF Check", "The current taxonomy is accepted and up to date.", parent=self.root)
            return

        if status == "SYNONYM":
            new_genus = res.get("genus", "")
            new_species = res.get("species", "")
            if new_species.startswith(new_genus + " "):
                # GBIF sometimes returns full species name (e.g., 'Puma concolor')
                new_species = new_species[len(new_genus)+1:]

            new_family = res.get("family", "")

            msg = f"Found a modern accepted name!\n\nOld: {old_genus} {old_species}\nNew: {new_genus} {new_species} ({new_family})\n\nWould you like to update? The old name will be saved in Notes/Variant."
            if messagebox.askyesno("Update Taxonomy", msg, parent=self.root):
                # Update UI vars
                if new_genus:
                    self.reg_vars["Genus"].set(new_genus)
                if new_species:
                    self.reg_vars["Species"].set(new_species)
                if new_family and "Family" in self.reg_vars:
                    self.reg_vars["Family"].set(new_family)

                # Save old name
                old_name_full = f"{old_genus} {old_species}".strip()
                if "Variant" in self.reg_vars:
                    v = self.reg_vars["Variant"].get()
                    self.reg_vars["Variant"].set((v + f" [Synonym: {old_name_full}]").strip())
                elif "Observation" in self.reg_vars:
                    v = self.reg_vars["Observation"].get()
                    self.reg_vars["Observation"].set((v + f" [Synonym: {old_name_full}]").strip())

                # Commit
                if hasattr(self, "commit_current_object"):
                    self.commit_current_object()

    def handle_gbif_autocomplete(self, event, field_name, entry_widget):
        # Allow standard navigation
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            if self._gbif_listbox and self._gbif_listbox.winfo_exists():
                if event.keysym == "Down":
                    self._gbif_listbox.focus_set()
                    self._gbif_listbox.selection_clear(0, tk.END)
                    self._gbif_listbox.selection_set(0)
                    self._gbif_listbox.activate(0)
            return

        if field_name not in ("Genus", "Species"):
            return

        query = entry_widget.get().strip()
        if len(query) < 3:
            self._close_gbif_listbox()
            return

        # Optional: Add Genus context if searching Species
        if field_name == "Species" and "Genus" in self.reg_vars:
            genus = self.reg_vars["Genus"].get().strip()
            if genus:
                query = f"{genus} {query}"

        if self._gbif_debounce_timer:
            self.root.after_cancel(self._gbif_debounce_timer)

        self._gbif_debounce_timer = self.root.after(400, lambda: self._do_gbif_autocomplete(query, entry_widget, field_name))

    def _do_gbif_autocomplete(self, query, entry_widget, field_name):
        def worker():
            results = self.gbif_query_suggest(query)
            if results:
                self.root.after(0, lambda: self._show_gbif_listbox(results, entry_widget, field_name))
            else:
                self.root.after(0, self._close_gbif_listbox)
        threading.Thread(target=worker, daemon=True).start()

    def _show_gbif_listbox(self, results, entry_widget, field_name):
        # Make sure widget is still focused
        if self.root.focus_get() != entry_widget:
            return

        self._close_gbif_listbox()

        self._gbif_listbox_window = tk.Toplevel(self.root)
        self._gbif_listbox_window.wm_overrideredirect(True)
        self._gbif_listbox_window.attributes('-topmost', True)

        # Position
        x = entry_widget.winfo_rootx()
        y = entry_widget.winfo_rooty() + entry_widget.winfo_height()
        self._gbif_listbox_window.geometry(f"+{x}+{y}")

        list_frame = tk.Frame(self._gbif_listbox_window, bg="#ffffff", highlightthickness=1, highlightbackground="#313244")
        list_frame.pack(fill="both", expand=True)

        self._gbif_listbox = tk.Listbox(
            list_frame,
            bg="#ffffff",
            fg="#1a1c1c",
            font=("Hanken Grotesk", sc(10)),
            selectbackground="#cdd6f4",
            selectforeground="#1a1c1c",
            relief="flat",
            bd=0,
            activestyle="none",
            height=min(len(results), 8),
            width=40
        )
        self._gbif_listbox.pack(fill="both", expand=True)

        self._gbif_suggestions_data = results
        for r in results:
            rank = r.get("rank", "").capitalize()
            name = r.get("scientificName", "")
            self._gbif_listbox.insert(tk.END, f"{name} ({rank})")

        self._gbif_listbox.bind("<ButtonRelease-1>", lambda e: self._on_gbif_select(entry_widget, field_name))
        self._gbif_listbox.bind("<FocusOut>", lambda e: self._close_gbif_listbox())

        # Bind keyboard events
        entry_widget.bind("<Down>", lambda e: self._gbif_listbox.focus_set(), add="+")
        self._gbif_listbox.bind("<Return>", lambda e: self._on_gbif_select(entry_widget, field_name))
        self._gbif_listbox.bind("<Escape>", lambda e: (self._close_gbif_listbox(), entry_widget.focus_set()))

        # Bind root click to close if not already bound
        if not getattr(self, "_gbif_click_bound", False):
            self.root.bind("<Button-1>", self._check_click_close_gbif, add="+")
            self._gbif_click_bound = True

    def _on_gbif_select(self, entry_widget, field_name):
        sel = self._gbif_listbox.curselection()
        if not sel:
            return

        idx = sel[0]
        data = self._gbif_suggestions_data[idx]

        # Populate fields
        genus = data.get("genus", "")
        species = data.get("species", "")
        family = data.get("family", "")

        if genus and "Genus" in self.reg_vars:
            self.reg_vars["Genus"].set(genus)

        if species and "Species" in self.reg_vars:
            if species.startswith(genus + " "):
                species = species[len(genus)+1:]
            self.reg_vars["Species"].set(species)

        if family and "Family" in self.reg_vars:
            self.reg_vars["Family"].set(family)

        self._close_gbif_listbox()
        if hasattr(self, "commit_current_object"):
            self.commit_current_object()

    def _close_gbif_listbox(self):
        if hasattr(self, "_gbif_listbox_window") and self._gbif_listbox_window:
            self._gbif_listbox_window.destroy()
            self._gbif_listbox_window = None
            self._gbif_listbox = None
        entry_widget.focus_set()

    def _check_click_close_gbif(self, event):
        if hasattr(self, "_gbif_listbox_window") and self._gbif_listbox_window:
            x, y = event.x_root, event.y_root
            x1 = self._gbif_listbox_window.winfo_rootx()
            y1 = self._gbif_listbox_window.winfo_rooty()
            x2 = x1 + self._gbif_listbox_window.winfo_width()
            y2 = y1 + self._gbif_listbox_window.winfo_height()

            if not (x1 <= x <= x2 and y1 <= y <= y2):
                self._close_gbif_listbox()
