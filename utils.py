import traceback

def debug_error(context, extra=""):
    msg = f"[ERROR] {context} {extra}\n{traceback.format_exc()}"
    print(msg)
    try:
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except:
        pass

def center_and_fit_toplevel(win, base_w=None, base_h=None):
    win.update_idletasks()
    
    req_w = base_w if base_w is not None else win.winfo_reqwidth()
    req_h = base_h if base_h is not None else win.winfo_reqheight()
    
    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()
    
    # Cap to 90% of screen height to avoid overflowing behind taskbars
    max_w = int(screen_w * 0.9)
    max_h = int(screen_h * 0.9)
    
    w = min(req_w, max_w)
    h = min(req_h, max_h)
    
    x = (screen_w // 2) - (w // 2)
    y = (screen_h // 2) - (h // 2)
    
    win.geometry(f"{w}x{h}+{x}+{y}")
