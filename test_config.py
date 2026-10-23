import unittest
from datetime import datetime
from unittest.mock import patch
import config

class TestConfigRecentFiles(unittest.TestCase):
    def setUp(self):
        # Reset the config cache before each test
        config._prefs_cache = None

    @patch('config.load_prefs')
    def test_get_recent_files_empty(self, mock_load):
        mock_load.return_value = {}
        self.assertEqual(config.get_recent_files(), [])

    @patch('config.load_prefs')
    def test_get_recent_files_populated(self, mock_load):
        mock_load.return_value = {"recent_files": [{"path": "/a.txt", "modified": "2023-01-01"}]}
        self.assertEqual(config.get_recent_files(), [{"path": "/a.txt", "modified": "2023-01-01"}])

    @patch('os.path.exists')
    @patch('config.save_prefs')
    @patch('config.load_prefs')
    def test_add_recent_file_invalid_path(self, mock_load, mock_save, mock_exists):
        mock_exists.return_value = False
        config.add_recent_file("/invalid.txt")
        mock_load.assert_not_called()
        mock_save.assert_not_called()

        config.add_recent_file("")
        mock_load.assert_not_called()
        mock_save.assert_not_called()

    @patch('os.path.exists')
    @patch('os.path.getmtime')
    @patch('config.save_prefs')
    @patch('config.load_prefs')
    def test_add_recent_file_new_file(self, mock_load, mock_save, mock_getmtime, mock_exists):
        mock_exists.return_value = True
        mock_getmtime.return_value = 1672531200 # 2023-01-01 00:00:00 UTC
        expected_date = datetime.fromtimestamp(1672531200).strftime("%Y-%m-%d")
        mock_load.return_value = {}

        config.add_recent_file("/new.txt")

        mock_save.assert_called_once()
        saved_prefs = mock_save.call_args[0][0]
        self.assertEqual(len(saved_prefs["recent_files"]), 1)
        self.assertEqual(saved_prefs["recent_files"][0]["path"], "/new.txt")
        # modified format is "%Y-%m-%d"
        self.assertEqual(saved_prefs["recent_files"][0]["modified"], expected_date)

    @patch('os.path.exists')
    @patch('os.path.getmtime')
    @patch('config.save_prefs')
    @patch('config.load_prefs')
    def test_add_recent_file_existing_file(self, mock_load, mock_save, mock_getmtime, mock_exists):
        mock_exists.return_value = True
        mock_getmtime.return_value = 1672617600 # 2023-01-02 00:00:00 UTC
        expected_date = datetime.fromtimestamp(1672617600).strftime("%Y-%m-%d")
        mock_load.return_value = {
            "recent_files": [
                {"path": "/old.txt", "modified": "2023-01-01"},
                {"path": "/new.txt", "modified": "2023-01-01"}
            ]
        }

        config.add_recent_file("/new.txt")

        mock_save.assert_called_once()
        saved_prefs = mock_save.call_args[0][0]
        self.assertEqual(len(saved_prefs["recent_files"]), 2)
        # Should be moved to top
        self.assertEqual(saved_prefs["recent_files"][0]["path"], "/new.txt")
        self.assertEqual(saved_prefs["recent_files"][0]["modified"], expected_date)
        self.assertEqual(saved_prefs["recent_files"][1]["path"], "/old.txt")

    @patch('os.path.exists')
    @patch('os.path.getmtime')
    @patch('config.save_prefs')
    @patch('config.load_prefs')
    def test_add_recent_file_exception_mtime(self, mock_load, mock_save, mock_getmtime, mock_exists):
        mock_exists.return_value = True
        mock_getmtime.side_effect = Exception("Permission denied")
        mock_load.return_value = {}

        config.add_recent_file("/err.txt")

        mock_save.assert_called_once()
        saved_prefs = mock_save.call_args[0][0]
        self.assertEqual(len(saved_prefs["recent_files"]), 1)
        self.assertEqual(saved_prefs["recent_files"][0]["path"], "/err.txt")
        self.assertEqual(saved_prefs["recent_files"][0]["modified"], "")

    @patch('os.path.exists')
    @patch('os.path.getmtime')
    @patch('config.save_prefs')
    @patch('config.load_prefs')
    def test_add_recent_file_limit(self, mock_load, mock_save, mock_getmtime, mock_exists):
        mock_exists.return_value = True
        mock_getmtime.return_value = 1672531200

        # 8 existing files
        initial_files = [{"path": f"/file{i}.txt", "modified": "2023-01-01"} for i in range(8)]
        mock_load.return_value = {"recent_files": initial_files}

        config.add_recent_file("/file8.txt")

        mock_save.assert_called_once()
        saved_prefs = mock_save.call_args[0][0]
        self.assertEqual(len(saved_prefs["recent_files"]), 8)
        self.assertEqual(saved_prefs["recent_files"][0]["path"], "/file8.txt")
        # The last file should be dropped (file7.txt since they are 0-7)
        self.assertEqual(saved_prefs["recent_files"][-1]["path"], "/file6.txt")

if __name__ == '__main__':
    unittest.main()
