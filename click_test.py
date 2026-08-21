import tkinter as tk
import time
from models import AppState
from ui.main_window import ObjectProgramUI
import ui.widgets
import config

old_see = ui.widgets.TreeviewListboxWrapper.see
def new_see(self, index_or_iid):
    print("----- SEE CALLED with", index_or_iid, "-----")
    import traceback
    traceback.print_stack()
    print("----------------------")
    return old_see(self, index_or_iid)
ui.widgets.TreeviewListboxWrapper.see = new_see

app = AppState()
import pandas as pd
app.df_reg = pd.DataFrame({'Genus': ['A', 'B', 'C'], 'Species': ['A', 'B', 'C']}, index=[1, 2, 3])
app.df_obs = pd.DataFrame({'Reviewed': [False, False, False]}, index=[1, 2, 3])
app.active_object_ids = [1, 2, 3]
app.list_view_mode = "detailed"
app.current_object_id = 1
app.config = list(config.DATABASE_CONFIGS.values())[0]

root = tk.Tk()
ui_inst = ObjectProgramUI(root, app)
ui_inst.reg_by_id = app.df_reg
ui_inst.obs_by_id = app.df_obs
ui_inst.build_ui()
ui_inst.refresh_list()

ui_inst.load_object = lambda oid: print(f"load_object({oid}) called!")

def do_click():
    print("Clicking on card 2!")
    ui_inst.object_list._on_card_click(2)

root.update_idletasks()
root.after(100, do_click)
root.after(1000, root.destroy)
root.mainloop()
