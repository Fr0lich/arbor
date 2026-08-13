from ui.image_handler import ImageHandlerMixin

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

class TestImageHandler:
    def test_image_next_prev(self):
        ui = DummyUI()
        ui._image_paths = ["img1.jpg", "img2.jpg"]
        ui._current_image_index = 0

        # We need to mock _render_image_gallery or it might fail trying to access tkinter
        def mock_render():
            pass
        ui._render_image_gallery = mock_render

        ui._next_image()
        assert ui._current_image_index == 1
        ui._prev_image()
        assert ui._current_image_index == 0

    def test_zoom_image(self):
        ui = DummyUI()
        ui.image_zoom_factor = 1.0
        ui._re_render_current_images = lambda: None

        ui.zoom_image_in()
        assert ui.image_zoom_factor == 1.25

        ui.zoom_image_out()
        assert ui.image_zoom_factor == 1.0

        for _ in range(20):
            ui.zoom_image_out()
        assert ui.image_zoom_factor == 0.1

    def test_rotate_image(self):
        ui = DummyUI()
        ui.image_rotation_angle = 0
        ui._re_render_current_images = lambda: None

        ui.rotate_image()
        assert ui.image_rotation_angle == 270

        ui.rotate_image()
        assert ui.image_rotation_angle == 180

        ui.rotate_image()
        assert ui.image_rotation_angle == 90

        ui.rotate_image()
        assert ui.image_rotation_angle == 0

    def test_reset_image_view(self):
        ui = DummyUI()
        ui.image_zoom_factor = 2.0
        ui.image_rotation_angle = 90
        ui._re_render_current_images = lambda: None

        ui.reset_image_view()
        assert ui.image_zoom_factor == 1.0
        assert ui.image_rotation_angle == 0

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
        assert ui.image_view_mode == "stack"

        ui.toggle_image_view()
        assert ui.image_view_mode == "gallery"

    def test_build_online_image_urls(self):
        ui = DummyUI()

        # Test default pattern or missing pattern
        ui.app.config["image_url_pattern"] = ""
        assert ui.build_online_image_urls("123") == []

        # Test {id} pattern
        ui.app.config["image_url_pattern"] = "https://example.com/img/{id}.jpg"
        urls = ui.build_online_image_urls("123")
        assert urls == [
            "https://example.com/img/123.jpg",
            "https://example.com/img/123-01.jpg",
            "https://example.com/img/123-02.jpg",
            "https://example.com/img/123-03.jpg"
        ]

        # Test {num} and {suffix} pattern (valid int)
        ui.app.config["image_url_pattern"] = "https://example.com/img/{num:04d}{suffix}.jpg"
        urls = ui.build_online_image_urls("42")
        assert urls == [
            "https://example.com/img/0042.jpg",
            "https://example.com/img/0042-01.jpg",
            "https://example.com/img/0042-02.jpg",
            "https://example.com/img/0042-03.jpg"
        ]

        # Test {num} and {suffix} pattern (invalid int fallback)
        urls = ui.build_online_image_urls("42A")
        # In the fallback, the implementation is f"{pattern.rstrip('/')}/{oid}{s}"
        assert urls == [
            "https://example.com/img/{num:04d}{suffix}.jpg/42A",
            "https://example.com/img/{num:04d}{suffix}.jpg/42A-01",
            "https://example.com/img/{num:04d}{suffix}.jpg/42A-02",
            "https://example.com/img/{num:04d}{suffix}.jpg/42A-03"
        ]

        # Test append pattern (no format strings)
        ui.app.config["image_url_pattern"] = "https://example.com/img/prefix-"
        urls = ui.build_online_image_urls("42")
        assert urls == [
            "https://example.com/img/prefix-42",
            "https://example.com/img/prefix-42-01",
            "https://example.com/img/prefix-42-02",
            "https://example.com/img/prefix-42-03"
        ]
