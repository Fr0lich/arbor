import pytest
import tkinter as tk
from ui.image_handler import ImageHandlerMixin
from models import AppState

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
