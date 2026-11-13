import unittest
from ui.image_handler import ImageHandlerMixin
from ui.image_panel import ImagePanel

class DummyApp:
    def __init__(self):
        self.config = {}
        self.df_obs = None

class DummyUI(ImageHandlerMixin):
    def __init__(self):
        self.app = DummyApp()
        self.image_mode = "folder"
        self._image_paths = []
        self._rendered_paths = None
        self._thumb_cards = []

class TestImageHandler(unittest.TestCase):
    def test_image_next_prev(self):
        ui = DummyUI()
        ui._image_paths = ["img1.jpg", "img2.jpg"]
        ui._current_image_index = 0

        def mock_render():
            pass
        ui._render_image_gallery = mock_render

        ui._next_image()
        self.assertEqual(ui._current_image_index, 1)
        ui._prev_image()
        self.assertEqual(ui._current_image_index, 0)

    def test_zoom_image(self):
        ui = DummyUI()
        ui.image_zoom_factor = 1.0
        ui._re_render_current_images = lambda: None

        ui.zoom_image_in()
        self.assertEqual(ui.image_zoom_factor, 1.25)

        ui.zoom_image_out()
        self.assertEqual(ui.image_zoom_factor, 1.0)

        for _ in range(20):
            ui.zoom_image_out()
        self.assertEqual(ui.image_zoom_factor, 0.1)

    def test_rotate_image(self):
        ui = DummyUI()
        ui.image_rotation_angle = 0
        ui._re_render_current_images = lambda: None

        ui.rotate_image()
        self.assertEqual(ui.image_rotation_angle, 270)

        ui.rotate_image()
        self.assertEqual(ui.image_rotation_angle, 180)

        ui.rotate_image()
        self.assertEqual(ui.image_rotation_angle, 90)

        ui.rotate_image()
        self.assertEqual(ui.image_rotation_angle, 0)

    def test_reset_image_view(self):
        ui = DummyUI()
        ui.image_zoom_factor = 2.0
        ui.image_rotation_angle = 90
        ui._re_render_current_images = lambda: None

        ui.reset_image_view()
        self.assertEqual(ui.image_zoom_factor, 1.0)
        self.assertEqual(ui.image_rotation_angle, 0)

    def test_toggle_image_view(self):
        ui = DummyUI()
        ui.image_view_mode = "gallery"
        ui.app.current_object_id = None

        class DummyBtn:
            def config(self, **kwargs):
                pass
        ui.view_btn = DummyBtn()
        ui.load_images = lambda oid: None

        ui.toggle_image_view()
        self.assertEqual(ui.image_view_mode, "stack")

        ui.toggle_image_view()
        self.assertEqual(ui.image_view_mode, "gallery")

    def test_build_online_image_urls(self):
        ui = DummyUI()

        ui.app.config["image_url_pattern"] = ""
        self.assertEqual(ui.build_online_image_urls("123"), [])

        ui.app.config["image_url_pattern"] = "https://example.com/img/{id}.jpg"
        urls = ui.build_online_image_urls("123")
        self.assertEqual(urls, [
            "https://example.com/img/123.jpg",
            "https://example.com/img/123-01.jpg",
            "https://example.com/img/123-02.jpg",
            "https://example.com/img/123-03.jpg"
        ])

        ui.app.config["image_url_pattern"] = "https://example.com/img/{num:04d}{suffix}.jpg"
        urls = ui.build_online_image_urls("42")
        self.assertEqual(urls, [
            "https://example.com/img/0042.jpg",
            "https://example.com/img/0042-01.jpg",
            "https://example.com/img/0042-02.jpg",
            "https://example.com/img/0042-03.jpg"
        ])

class TestImagePanel(unittest.TestCase):
    def test_panel_zoom_rotate_reset(self):
        panel = ImagePanel.__new__(ImagePanel)
        panel.image_zoom_factor = 1.0
        panel.image_rotation_angle = 0
        panel.app = DummyApp()
        panel._re_render_current_images = lambda: None

        panel.zoom_image_in()
        self.assertEqual(panel.image_zoom_factor, 1.25)

        panel.zoom_image_out()
        self.assertEqual(panel.image_zoom_factor, 1.0)

        panel.rotate_image(90)
        self.assertEqual(panel.image_rotation_angle, 90)

        panel.reset_image_view()
        self.assertEqual(panel.image_zoom_factor, 1.0)
        self.assertEqual(panel.image_rotation_angle, 0)

    def test_panel_online_url_building(self):
        panel = ImagePanel.__new__(ImagePanel)
        panel.app = DummyApp()
        panel.app.config["image_url_pattern"] = "https://example.com/img/{id}.jpg"
        urls = panel.build_online_image_urls("99")
        self.assertEqual(urls[0], "https://example.com/img/99.jpg")

    def test_toggle_image_tools(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            panel = ImagePanel(root)
            panel.show_image_tools_var.set(True)
            panel.toggle_image_tools()
            self.assertEqual(panel.image_toolbar.winfo_manager(), "pack")

            panel.show_image_tools_var.set(False)
            panel.toggle_image_tools()
            self.assertEqual(panel.image_toolbar.winfo_manager(), "")
        finally:
            root.destroy()


class TestMainWindowImageDelegation(unittest.TestCase):
    def test_main_window_image_box_and_toggle_tools(self):
        import tkinter as tk
        from ui.main_window import ObjectProgramUI
        root = tk.Tk()
        root.withdraw()
        try:
            panel = ImagePanel(root)
            mw = ObjectProgramUI.__new__(ObjectProgramUI)
            mw.image_panel = panel
            
            # Verify image_box property delegation
            self.assertIsNotNone(mw.image_box)
            self.assertEqual(mw.image_box, panel.image_box)

            # Verify toggle_image_tools delegation without AttributeError
            mw.show_image_tools_var.set(True)
            mw.toggle_image_tools()
            self.assertEqual(panel.image_toolbar.winfo_manager(), "pack")

            mw.show_image_tools_var.set(False)
            mw.toggle_image_tools()
            self.assertEqual(panel.image_toolbar.winfo_manager(), "")
        finally:
            root.destroy()




class TestAsyncGBIFWorkflows(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from unittest.mock import MagicMock
        from ui.main_window import ObjectProgramUI
        self.root = tk.Tk()
        self.root.withdraw()
        self.mw = ObjectProgramUI.__new__(ObjectProgramUI)
        self.mw.root = self.root
        self.mw.app = MagicMock()
        self.mw.app.current_object_id = "12345"
        self.mw.reg_vars = {
            "Genus": tk.StringVar(),
            "Species": tk.StringVar()
        }
        self.mw.gbif_btn = MagicMock()
        self.mw.gbif_btn.winfo_exists.return_value = True

    def tearDown(self):
        self.root.destroy()

    def test_check_gbif_missing_genus_shows_toast_not_messagebox(self):
        from unittest.mock import patch
        with patch("ui.toast.ToastManager.show") as mock_toast,              patch("tkinter.messagebox.showinfo") as mock_msgbox:
            self.mw.reg_vars["Genus"].set("")
            self.mw.check_gbif_action()

            mock_msgbox.assert_not_called()
            mock_toast.assert_called_once_with(self.root, "Genus is required for GBIF verification", toast_type="warning")

    def test_check_gbif_dispatches_app_worker(self):
        from unittest.mock import patch
        with patch("ui.toast.ToastManager.show") as mock_toast,              patch("tkinter.messagebox.showwarning") as mock_warn,              patch("backend.task_queue.app_worker.run_in_background") as mock_run_bg:
            self.mw.reg_vars["Genus"].set("Betula")
            self.mw.reg_vars["Species"].set("pendula")
            self.mw.check_gbif_action()

            mock_warn.assert_not_called()
            self.assertTrue(mock_run_bg.called)
            self.mw.gbif_btn.config.assert_called_with(text="Loading...", bg="#6c757d")

    def test_gbif_no_match_shows_toast_not_messagebox(self):
        from unittest.mock import patch
        with patch("ui.toast.ToastManager.show") as mock_toast,              patch("tkinter.messagebox.showwarning") as mock_warn:
            self.mw._on_gbif_result(None, "Unknown", "species")
            mock_warn.assert_not_called()
            mock_toast.assert_called_once_with(self.root, "No match found in GBIF Backbone Taxonomy", toast_type="warning")

    def test_gbif_network_error_shows_toast_not_messagebox(self):
        from unittest.mock import patch
        with patch("ui.toast.ToastManager.show") as mock_toast,              patch("tkinter.messagebox.showerror") as mock_err:
            self.mw._on_gbif_result({"error": "Timeout 504"}, "Betula", "pendula")
            mock_err.assert_not_called()
            mock_toast.assert_called_once_with(self.root, "GBIF connection error: Timeout 504", toast_type="error")

    def test_gbif_exception_handler_shows_toast_not_messagebox(self):
        from unittest.mock import patch
        with patch("ui.toast.ToastManager.show") as mock_toast,              patch("tkinter.messagebox.showerror") as mock_err:
            self.mw._on_gbif_error("DNS resolution failed")
            mock_err.assert_not_called()
            mock_toast.assert_called_once_with(self.root, "GBIF connection error: DNS resolution failed", toast_type="error")

    def test_gbif_synonym_fetches_accepted_name_via_app_worker(self):
        from unittest.mock import patch
        with patch("backend.task_queue.app_worker.run_in_background") as mock_run_bg:
            result = {"synonym": True, "acceptedUsageKey": 98765}
            self.mw._on_gbif_result(result, "Betula", "alba")
            self.assertTrue(mock_run_bg.called)


class TestAsyncImageTasks(unittest.TestCase):
    def test_image_panel_tasks_route_through_app_worker(self):
        import tkinter as tk
        from unittest.mock import patch, MagicMock
        root = tk.Tk()
        root.withdraw()
        try:
            panel = ImagePanel(root)
            with patch("backend.task_queue.app_worker.run_in_background") as mock_run_bg,                  patch("tkinter.filedialog.askdirectory", return_value="C:/herbarium_images"):
                panel.select_image_folder()
                self.assertTrue(mock_run_bg.called)

            with patch("backend.task_queue.app_worker.run_in_background") as mock_run_bg:
                mock_label = MagicMock()
                mock_label.winfo_exists.return_value = True
                panel._load_image_async("C:/herbarium_images/123.jpg", False, mock_label)
                self.assertTrue(mock_run_bg.called)

            with patch("backend.task_queue.app_worker.run_in_background") as mock_run_bg:
                panel.app = MagicMock()
                panel.app.config = {"has_images": True}
                panel.app.active_object_ids = ["122", "123", "124"]
                panel.image_mode = "folder"
                panel.show_images_var.set(True)
                panel.image_index = {"124": ["C:/herbarium_images/124.jpg"]}
                panel._preload_adjacent_images("123")
                self.assertTrue(mock_run_bg.called)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()


