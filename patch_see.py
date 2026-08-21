import ui.widgets
import traceback

old_see = ui.widgets.TreeviewListboxWrapper.see
def new_see(self, index_or_iid):
    print("----- SEE CALLED -----")
    traceback.print_stack()
    print("----------------------")
    return old_see(self, index_or_iid)

ui.widgets.TreeviewListboxWrapper.see = new_see
