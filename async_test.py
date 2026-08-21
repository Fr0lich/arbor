import tkinter as tk
from tkinter import ttk

root = tk.Tk()
tree = ttk.Treeview(root)
tree.pack()
tree.insert("", "end", iid="A", text="Item A")
tree.insert("", "end", iid="B", text="Item B")

sync_flag = True

def on_select(event):
    print("on_select called! sync_flag is:", sync_flag)

tree.bind("<<TreeviewSelect>>", on_select)

def click_sim():
    global sync_flag
    sync_flag = True
    print("Calling selection_set...")
    tree.selection_set("B")
    print("selection_set returned.")
    sync_flag = False

root.after(100, click_sim)
root.after(500, root.destroy)
root.mainloop()
