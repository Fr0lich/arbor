import cProfile
import time
from ui.widgets import TreeviewListboxWrapper
import tkinter as tk

class MockApp:
    df_photo = None

class MockMainWindow:
    def __init__(self, root):
        self.dark_mode_active = False
        self.app = MockApp()
        self.image_index = {}
        self._get_obs_dict = lambda: {}
        self._get_reg_dict = lambda: {}
        self._get_cached_problem = lambda x: False
        self._has_history = lambda x: False
        self._problems_have_history = lambda x: False
        self.focus_mode_var = tk.StringVar(value="off")

root = tk.Tk()
import config
config.sc = lambda x: x

mw = MockMainWindow(root)
view = TreeviewListboxWrapper(root, mw, bg="black")
view.pack(fill="both", expand=True)

view.items_list = [str(i) for i in range(2000)]
view.item_data = {str(i): {"tags": [], "values": [], "title": str(i)} for i in range(2000)}
view.active_view = "detailed"
view._card_height = 80
view.canvas.configure(height=800, width=500)
root.update()

def scroll_fast():
    for i in range(1, 10):
        view.canvas.yview_moveto((i * 10) / 2000)
        view._update_visible_cards()
        view.update_idletasks()

    for i in range(10, 20):
        view.canvas.yview_moveto((i * 10) / 2000)
        view._update_visible_cards()
        view.update_idletasks()

cProfile.run('scroll_fast()', 'scroll.prof')
import pstats
p = pstats.Stats('scroll.prof')
p.sort_stats('cumtime').print_stats(15)

root.destroy()
