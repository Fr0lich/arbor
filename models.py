import pandas as pd
import threading


class AppState:
    """Central application state passed between the UI and data layers.

    All attributes are initialised to None/empty here so that accidental access
    before a file is loaded raises an AttributeError rather than reading a
    shared class-level default from a previous session.
    """

    def __init__(self):
        # Active database config dict (from config.DATABASE_CONFIGS)
        self.config: dict | None = None
        # Human-readable name of the active config
        self.config_name: str | None = None

        # Path to the source file that was opened
        self.excel_path: str | None = None
        # Path where saves are written (may differ from excel_path)
        self.output_path: str | None = None

        # Primary dataframes (indexed by ObjectID after load)
        self.df_reg: pd.DataFrame | None = None
        self.df_obs: pd.DataFrame | None = None
        self.df_photo: pd.DataFrame | None = None
        self.df_log: pd.DataFrame | None = None

        # Snapshot of df_obs at load time, used to detect changes
        self.initial_df_obs: pd.DataFrame | None = None

        # Ordered list of ObjectIDs currently visible in the object list
        self.active_object_ids: list[str] = []

        # ObjectID of the item currently displayed in the detail panel
        self.current_object_id: str | None = None

        # True when there are unsaved changes
        self.dirty: bool = False

        # List of additional historical database dicts for comparison
        self.historical_dbs: list[dict] = []

        # Per-ObjectID undo/redo stacks: {oid: [state_dict, ...]}
        self.undo_stacks: dict[str, list[dict]] = {}
        self.redo_stacks: dict[str, list[dict]] = {}

        # P1-B: Protects df_reg/df_obs/df_photo/df_log during background copy.
        # Use acquire() before .copy() in any worker thread to avoid read-during-write
        # races when the main thread commits an edit mid-save.
        self.df_lock: threading.RLock = threading.RLock()


# P1-F: Single source of truth for per-object undo stack depth.
# Keeping 20 states per object × 3000 objects worst-case = ~60k entries
# which is negligible memory; the global 500-entry total guard is retained.
MAX_UNDO_PER_OBJECT: int = 20
