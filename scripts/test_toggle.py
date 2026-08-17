import tkinter as tk
from ui.widgets import ToggleSwitch

def main():
    root = tk.Tk()
    var = tk.BooleanVar()
    ToggleSwitch(root, var).pack(padx=20, pady=20)
    tk.Entry(root).pack()
    root.after(1000, root.destroy)
    root.mainloop()

if __name__ == "__main__":
    main()
