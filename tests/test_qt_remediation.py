"""Unit tests for Arbor PySide6 Remediation (Observations 1-5).

Tests:
1. Multi-image thumbnail strip, card creation, and gallery navigation (Observation 1).
2. Filter dialog index caching and debouncing (Observation 2).
3. Tree widget uniformRowHeights and O(1) index caching (Observation 3).
4. Object list problem indicators (marks '⚠', '✓', '⚠✓') and foreground colors (Observation 4).
5. History button wiring to historical conflict resolver (Observation 5).
"""
import os
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsView,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from models import AppState
from repository import REVIEWED_COLUMN
from ui_qt.image_viewer import QtImageViewer, QtThumbnailCard, QtThumbnailStrip
from ui_qt.main_window import QtMainWindow


class TestQtRemediation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.app_state = AppState()
        self.app_state.config = {
            "ui_sections": {
                "problems": [
                    {"name": "Taxonomy_Problem", "maps_to": "Genus"},
                    {"name": "Other_problem", "maps_to": "Other"},
                ]
            }
        }

        # Setup test dataframes
        df_reg = pd.DataFrame(
            [
                {"ObjectID": "1001", "Genus": "Betula", "Species": "pendula"},
                {"ObjectID": "1002", "Genus": "Pinus", "Species": "sylvestris"},
                {"ObjectID": "1003", "Genus": "Quercus", "Species": "robur"},
                {"ObjectID": "1004", "Genus": "Acer", "Species": "platanoides"},
            ]
        ).set_index("ObjectID")

        df_obs = pd.DataFrame(
            [
                {"ObjectID": "1001", REVIEWED_COLUMN: False, "Taxonomy_Problem": True, "Other_problem": False},
                {"ObjectID": "1002", REVIEWED_COLUMN: True, "Taxonomy_Problem": True, "Other_problem": False},
                {"ObjectID": "1003", REVIEWED_COLUMN: True, "Taxonomy_Problem": False, "Other_problem": False},
                {"ObjectID": "1004", REVIEWED_COLUMN: False, "Taxonomy_Problem": False, "Other_problem": False},
            ]
        ).set_index("ObjectID")

        self.app_state.df_reg = df_reg
        self.app_state.df_obs = df_obs
        self.app_state.active_object_ids = ["1001", "1002", "1003", "1004"]
        self.app_state.current_object_id = "1001"

    # -------------------------------------------------------------------------
    # Observation 1: Image Navigation & Thumbnail Strip
    # -------------------------------------------------------------------------
    def test_thumbnail_strip_and_navigation(self):
        """Verify thumbnail strip instantiation, card creation, and image cycling."""
        container = QWidget()
        layout = QVBoxLayout(container)
        view = QGraphicsView(container)
        layout.addWidget(view)

        viewer = QtImageViewer(graphics_view=view)
        self.assertIsNotNone(viewer.thumb_strip)

        # Mock image paths
        dummy_images = ["img1.jpg", "img2.jpg", "img3.jpg"]
        viewer.image_paths = dummy_images
        viewer.current_image_index = 0
        viewer.thumb_strip.set_images(dummy_images, 0)

        # Thumbnail strip should be visible for multiple images
        self.assertTrue(viewer.thumb_strip.isVisible())
        self.assertEqual(len(viewer.thumb_strip.cards), 3)
        self.assertTrue(viewer.thumb_strip.cards[0].is_active)
        self.assertFalse(viewer.thumb_strip.cards[1].is_active)

        # Test selecting image by index
        viewer.select_image(1)
        self.assertEqual(viewer.current_image_index, 1)
        self.assertFalse(viewer.thumb_strip.cards[0].is_active)
        self.assertTrue(viewer.thumb_strip.cards[1].is_active)

        # Test cycling next
        viewer.next_image()
        self.assertEqual(viewer.current_image_index, 2)
        self.assertTrue(viewer.thumb_strip.cards[2].is_active)

        # Test cycling prev
        viewer.prev_image()
        self.assertEqual(viewer.current_image_index, 1)
        self.assertTrue(viewer.thumb_strip.cards[1].is_active)

        # Single image should hide thumbnail strip
        viewer.thumb_strip.set_images(["single.jpg"], 0)
        self.assertFalse(viewer.thumb_strip.isVisible())

    def test_image_dir_caching(self):
        """Verify local image directory is indexed once into cache."""
        view = QGraphicsView()
        viewer = QtImageViewer(graphics_view=view)

        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["1001_1.jpg", "1001_2.png", "1002.jpg"]) as mock_listdir:

            # First query populates cache
            files = viewer._get_local_images_for_specimen("/fake/dir", "1001")
            self.assertEqual(len(files), 2)
            self.assertEqual(mock_listdir.call_count, 1)

            # Second query uses cache without calling listdir
            files2 = viewer._get_local_images_for_specimen("/fake/dir", "1001")
            self.assertEqual(len(files2), 2)
            self.assertEqual(mock_listdir.call_count, 1)

    # -------------------------------------------------------------------------
    # Observation 2: Filter Dialog Index Caching & Debouncing
    # -------------------------------------------------------------------------
    def test_filter_dialog_index_caching(self):
        """Verify FilterDialog caches dict conversions across match computations."""
        from ui_qt.filter_dialog import QtFilterDialog

        dlg = QtFilterDialog(app_state=self.app_state)
        self.assertIsNotNone(dlg._debounce_timer)
        self.assertTrue(dlg._debounce_timer.isSingleShot())
        self.assertEqual(dlg._debounce_timer.interval(), 180)

        # Initial compute creates cached dictionaries
        self.assertIsNone(dlg._reg_dict)
        matches1 = dlg._compute_matches()
        self.assertIsNotNone(dlg._reg_dict)
        self.assertIsNotNone(dlg._obs_dict)

        # Re-computing should reuse cached dictionaries
        with patch.object(self.app_state.df_reg, "to_dict") as mock_to_dict:
            matches2 = dlg._compute_matches()
            self.assertEqual(matches1, matches2)
            mock_to_dict.assert_not_called()

    # -------------------------------------------------------------------------
    # Observation 3: Tree Uniform Row Heights & O(1) Index Lookup
    # -------------------------------------------------------------------------
    def test_tree_uniform_row_heights_and_indexing(self):
        """Verify uniformRowHeights is enabled and O(1) position map is populated."""
        controller = QtMainWindow(self.app_state)
        tree = controller.win.tree_objects

        self.assertTrue(tree.uniformRowHeights())

        controller.refresh_object_tree()
        self.assertEqual(controller._active_id_indices.get("1001"), 0)
        self.assertEqual(controller._active_id_indices.get("1002"), 1)
        self.assertEqual(controller._active_id_indices.get("1003"), 2)
        self.assertEqual(controller._active_id_indices.get("1004"), 3)

    # -------------------------------------------------------------------------
    # Observation 4: Object List Problem Indicators & Colors
    # -------------------------------------------------------------------------
    def test_object_list_problem_indicators_and_colors(self):
        """Verify problem badges and colors:
        - 1001: Unreviewed + Problem -> '⚠' (Red #d9534f)
        - 1002: Reviewed + Problem   -> '⚠✓' (Amber #d9a036)
        - 1003: Reviewed + Clean     -> '✓' (Green #2e7d32)
        - 1004: Unreviewed + Clean   -> ' ' (Default)
        """
        controller = QtMainWindow(self.app_state)
        controller.refresh_object_tree()
        tree = controller.win.tree_objects

        self.assertEqual(tree.topLevelItemCount(), 4)

        item_1001 = tree.topLevelItem(0)
        item_1002 = tree.topLevelItem(1)
        item_1003 = tree.topLevelItem(2)
        item_1004 = tree.topLevelItem(3)

        # 1001: Unreviewed problem
        self.assertEqual(item_1001.text(0), "⚠")
        self.assertEqual(item_1001.text(1), "1001")
        self.assertEqual(item_1001.foreground(0).color().name(), "#d9534f")

        # 1002: Reviewed problem
        self.assertEqual(item_1002.text(0), "⚠✓")
        self.assertEqual(item_1002.text(1), "1002")
        self.assertEqual(item_1002.foreground(0).color().name(), "#d9a036")

        # 1003: Reviewed clean
        self.assertEqual(item_1003.text(0), "✓")
        self.assertEqual(item_1003.text(1), "1003")
        self.assertEqual(item_1003.foreground(0).color().name(), "#2e7d32")

        # 1004: Unreviewed clean
        self.assertEqual(item_1004.text(0), " ")
        self.assertEqual(item_1004.text(1), "1004")

        # Test dynamic update when problem is toggled
        controller.navigate_to_object("1004")
        controller._on_problem_toggled("Taxonomy_Problem", True)
        self.assertEqual(item_1004.text(0), "⚠")
        self.assertEqual(item_1004.foreground(0).color().name(), "#d9534f")

        # Test dynamic update when reviewed is toggled
        controller.toggle_reviewed()
        self.assertEqual(item_1004.text(0), "⚠✓")
        self.assertEqual(item_1004.foreground(0).color().name(), "#d9a036")

    # -------------------------------------------------------------------------
    # Observation 5: History Button Rewiring
    # -------------------------------------------------------------------------
    def test_history_button_wiring(self):
        """Verify btn_history opens historical conflict resolver for current specimen."""
        controller = QtMainWindow(self.app_state)

        with patch.object(controller, "open_historical_resolver_for_current") as mock_resolver:
            controller.win.btn_history.click()
            mock_resolver.assert_called_once()


if __name__ == "__main__":
    unittest.main()
