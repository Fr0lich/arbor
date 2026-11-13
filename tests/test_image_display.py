"""Unit tests for Arbor Image Inspection Canvas, Zoom Ergonomics, and Async Pre-Caching.

Verifies:
1. Graceful placeholder canvas rendering when image files are missing from disk or corrupted,
   with zero mainloop crashes and explanatory badge: 'Image not found on disk: [filename]'.
2. Conflict-free zoom presets (Ctrl+1 Fit Window, Ctrl+2 Fit Width, Ctrl+3 100% 1:1 Actual Pixels)
   with mathematical scale factor correctness and zero clashing with ui/keybindings.py shortcuts.
3. Cachetools LRUCache eviction discipline with maxsize=10 capacity.
"""

import os
import time
import tempfile
import tkinter as tk
from unittest.mock import MagicMock
from PIL import Image

from ui.image_handler import (
    ImagePreCacher,
    create_missing_image_placeholder
)
from ui.image_panel import ImagePanel
from ui.keybindings import KeybindingManager, CANONICAL_SHORTCUTS


def _wait_for_condition(root, predicate, panel=None, timeout=5.0):
    start = time.time()
    while time.time() - start < timeout:
        if panel and hasattr(panel, "_poll_ui_queue"):
            panel._poll_ui_queue()
        root.update_idletasks()
        root.update()
        if predicate():
            return True
        time.sleep(0.02)
    if panel and hasattr(panel, "_poll_ui_queue"):
        panel._poll_ui_queue()
    return predicate()


def test_missing_and_corrupted_image_displays_graceful_placeholder():
    """Verify missing or corrupted image files render a graceful placeholder without crashing."""
    root = tk.Tk()
    root.withdraw()
    try:
        # 1. Test visual placeholder image generator
        missing_filename = "non_existent_specimen_12345.jpg"
        placeholder = create_missing_image_placeholder(missing_filename, width=400, height=300)
        assert placeholder is not None
        assert isinstance(placeholder, Image.Image)
        assert placeholder.size == (400, 300)

        # 2. Test ImagePanel handling of missing file path
        panel = ImagePanel(root)
        mock_label = tk.Label(panel)
        missing_path = "C:/herbarium_scans/ghost_specimen_99999.jpg"
        mock_label.loading_path = missing_path

        # Async load on non-existent file should not raise FileNotFoundError or crash
        panel._load_image_async(missing_path, large=True, target_widget=mock_label)
        success = _wait_for_condition(root, lambda: hasattr(mock_label, "image"), panel=panel)
        assert success, "Expected mock_label to receive placeholder image within timeout"

        assert mock_label.image is not None
        assert "Image not found on disk" in panel.images_missing_label.cget("text")
        assert "ghost_specimen_99999.jpg" in panel.images_missing_label.cget("text")

        # 3. Test corrupted image file resilience
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as corrupt_file:
            corrupt_file.write(b"CORRUPTED_NON_IMAGE_DATA_BYTES")
            corrupt_path = corrupt_file.name

        try:
            panel_corrupt = ImagePanel(root)
            corrupt_label = tk.Label(panel_corrupt)
            corrupt_label.loading_path = corrupt_path
            panel_corrupt._load_image_async(corrupt_path, large=True, target_widget=corrupt_label)
            success_corrupt = _wait_for_condition(root, lambda: hasattr(corrupt_label, "image"), panel=panel_corrupt)
            assert success_corrupt, "Expected corrupt_label to receive placeholder image within timeout"
            assert corrupt_label.image is not None
        finally:
            if os.path.exists(corrupt_path):
                os.remove(corrupt_path)
    finally:
        root.destroy()


def test_zoom_presets_scale_factors_and_no_keybinding_clash():
    """
    Verify Ctrl+1, Ctrl+2, Ctrl+3 calculate expected scale factors and do not
    clash with existing shortcuts in ui/keybindings.py.
    """
    root = tk.Tk()
    root.withdraw()
    try:
        panel = ImagePanel(root)
        panel._image_paths = ["test_herbarium_sheet.jpg"]
        panel._current_image_index = 0

        # Supply mock pre-decoded 2000x3000 portrait herbarium scan
        dummy_scan = Image.new("RGB", (2000, 3000), color="green")
        panel.pre_cacher.put("test_herbarium_sheet.jpg", dummy_scan)

        # 1. Scale factor calculations
        scales = panel.calculate_zoom_preset_scales("test_herbarium_sheet.jpg")
        assert "fit_window" in scales
        assert "fit_width" in scales
        assert "actual_pixels" in scales

        # Fit Window is 1.0 (entire sheet visible)
        assert scales["fit_window"] == 1.0
        # Fit Width expands to match canvas width (greater than window fit)
        assert scales["fit_width"] > 1.0
        # 100% 1:1 Actual Pixels is largest magnification
        assert scales["actual_pixels"] >= scales["fit_width"]

        # 2. Preset activation methods
        panel.zoom_fit_window()
        assert panel.image_zoom_factor == 1.0

        panel.zoom_fit_width()
        assert panel.image_zoom_factor == scales["fit_width"]

        panel.zoom_actual_pixels()
        assert panel.image_zoom_factor == scales["actual_pixels"]

        # Ctrl+0 reset_image_view preserved
        panel.reset_image_view()
        assert panel.image_zoom_factor == 1.0
        assert panel.image_rotation_angle == 0

        # 3. Shortcut anti-collision audit with ui/keybindings.py
        bound_keys = root.bind()

        # Ensure preserved shortcuts and new presets are bound
        assert "<Control-Key-0>" in bound_keys or "<Control-0>" in bound_keys
        assert "<Control-Key-1>" in bound_keys or "<Control-1>" in bound_keys
        assert "<Control-Key-2>" in bound_keys or "<Control-2>" in bound_keys
        assert "<Control-Key-3>" in bound_keys or "<Control-3>" in bound_keys

        # Verify no clashing: Ctrl+1, Ctrl+2, Ctrl+3 are NOT clobbering Primary Work Keys
        primary_shortcuts = [item[1] for item in CANONICAL_SHORTCUTS if item[0] == "PRIMARY WORK KEYS"]
        primary_str = " ".join(primary_shortcuts)
        assert "Ctrl + 1" not in primary_str
        assert "Ctrl + 2" not in primary_str
        assert "Ctrl + 3" not in primary_str

        # Preserved critical shortcuts in CANONICAL_SHORTCUTS
        assert "ENTER" in primary_str or "R" in primary_str
        assert "SPACE" in primary_str
    finally:
        root.destroy()


def test_image_pre_cacher_lru_eviction():
    """Verify cachetools LRUCache evicts oldest items when capacity (10) is reached."""
    pre_cacher = ImagePreCacher(maxsize=10)
    assert pre_cacher.maxsize == 10
    assert len(pre_cacher) == 0

    # Populate with 10 dummy images
    dummy_images = {}
    for i in range(1, 11):
        path = f"/scans/specimen_{i:03d}.jpg"
        img = Image.new("RGB", (64, 64), color=(i * 10, i * 10, i * 10))
        dummy_images[path] = img
        pre_cacher.put(path, img)

    assert len(pre_cacher) == 10
    assert "/scans/specimen_001.jpg" in pre_cacher

    # Insert 11th image -> specimen_001.jpg should be evicted
    img_11 = Image.new("RGB", (64, 64), color="blue")
    pre_cacher.put("/scans/specimen_011.jpg", img_11)

    assert len(pre_cacher) == 10
    assert "/scans/specimen_001.jpg" not in pre_cacher
    assert "/scans/specimen_011.jpg" in pre_cacher

    # Access specimen_002.jpg to make it most recently used
    accessed = pre_cacher.get("/scans/specimen_002.jpg")
    assert accessed is not None

    # Insert 12th image -> specimen_003.jpg should be evicted next (since 002 was recently accessed)
    img_12 = Image.new("RGB", (64, 64), color="yellow")
    pre_cacher.put("/scans/specimen_012.jpg", img_12)

    assert len(pre_cacher) == 10
    assert "/scans/specimen_003.jpg" not in pre_cacher
    assert "/scans/specimen_002.jpg" in pre_cacher
    assert "/scans/specimen_012.jpg" in pre_cacher
