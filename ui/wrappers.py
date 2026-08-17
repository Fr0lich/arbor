class LabelWrapper:
    def __init__(self, real_label, ui):
        self.real = real_label
        self.ui = ui

    def config(self, cnf=None, **kw):
        if cnf is not None:
            kw.update(cnf)
        text = kw.get("text")
        if text is not None:
            if hasattr(self.ui, "_loading_window") and self.ui._loading_window and self.ui._loading_window.win.winfo_exists():
                self.ui._loading_window.update_status_text(text)
        try:
            return self.real.config(**kw)
        except Exception:
            pass

    def configure(self, cnf=None, **kw):
        return self.config(cnf, **kw)

    def cget(self, option):
        return self.real.cget(option)

    def __getitem__(self, key):
        return self.real[key]

    def __setitem__(self, key, value):
        self.real[key] = value
        if key == "text":
            if hasattr(self.ui, "_loading_window") and self.ui._loading_window and self.ui._loading_window.win.winfo_exists():
                self.ui._loading_window.update_status_text(value)

    def __getattr__(self, name):
        return getattr(self.real, name)


class ProgressbarWrapper:
    def __init__(self, real_progressbar, ui):
        self.real = real_progressbar
        self.ui = ui

    def configure(self, cnf=None, **kw):
        if cnf is not None:
            kw.update(cnf)
        value = kw.get("value")
        maximum = kw.get("maximum")

        if hasattr(self.ui, "_loading_window") and self.ui._loading_window and self.ui._loading_window.win.winfo_exists():
            self.ui._loading_window.update_progress_bar(value, maximum)
        try:
            return self.real.configure(**kw)
        except Exception:
            pass

    def config(self, cnf=None, **kw):
        return self.configure(cnf, **kw)

    def cget(self, option):
        return self.real.cget(option)

    def __getitem__(self, key):
        return self.real[key]

    def __setitem__(self, key, value):
        self.real[key] = value
        if key == "value":
            if hasattr(self.ui, "_loading_window") and self.ui._loading_window and self.ui._loading_window.win.winfo_exists():
                self.ui._loading_window.update_progress_bar(value=value)

    def __getattr__(self, name):
        return getattr(self.real, name)
