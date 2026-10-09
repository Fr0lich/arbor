"""Tests for the dual UI startup selection mechanism in main.py."""
import unittest
from unittest.mock import patch
import sys

from main import select_ui_framework


class TestStartupSelection(unittest.TestCase):
    """Verify CLI flags, env vars, interactive prompt, and defaults."""

    def test_cli_flag_ui_qt(self):
        argv = ["main.py", "--ui", "qt"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=False)
        self.assertEqual(choice, "qt")
        self.assertEqual(argv, ["main.py"])

    def test_cli_flag_ui_tk(self):
        argv = ["main.py", "--ui", "tk"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=False)
        self.assertEqual(choice, "tk")
        self.assertEqual(argv, ["main.py"])

    def test_cli_flag_equals_qt(self):
        argv = ["main.py", "--ui=qt"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=False)
        self.assertEqual(choice, "qt")
        self.assertEqual(argv, ["main.py"])

    def test_cli_flag_equals_tk(self):
        argv = ["main.py", "--ui=tk"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=False)
        self.assertEqual(choice, "tk")
        self.assertEqual(argv, ["main.py"])

    def test_cli_flag_shorthand_qt(self):
        argv = ["main.py", "--qt"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=False)
        self.assertEqual(choice, "qt")
        self.assertEqual(argv, ["main.py"])

    def test_cli_flag_shorthand_tk(self):
        argv = ["main.py", "--tk"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=False)
        self.assertEqual(choice, "tk")
        self.assertEqual(argv, ["main.py"])

    def test_cli_flag_pyside6_alias(self):
        argv = ["main.py", "--ui", "pyside6"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=False)
        self.assertEqual(choice, "qt")

    def test_env_var_qt(self):
        argv = ["main.py"]
        env = {"ARBOR_UI": "qt"}
        choice = select_ui_framework(argv=argv, env=env, is_interactive=False)
        self.assertEqual(choice, "qt")

    def test_env_var_tk(self):
        argv = ["main.py"]
        env = {"ARBOR_UI": "tk"}
        choice = select_ui_framework(argv=argv, env=env, is_interactive=False)
        self.assertEqual(choice, "tk")

    def test_cli_overrides_env_var(self):
        argv = ["main.py", "--ui", "tk"]
        env = {"ARBOR_UI": "qt"}
        choice = select_ui_framework(argv=argv, env=env, is_interactive=False)
        self.assertEqual(choice, "tk")

    def test_non_interactive_defaults_to_tk(self):
        argv = ["main.py"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=False)
        self.assertEqual(choice, "tk")

    @patch("builtins.input", return_value="2")
    def test_interactive_prompt_choose_qt(self, mock_input):
        argv = ["main.py"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=True)
        self.assertEqual(choice, "qt")

    @patch("builtins.input", return_value="1")
    def test_interactive_prompt_choose_tk(self, mock_input):
        argv = ["main.py"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=True)
        self.assertEqual(choice, "tk")

    @patch("builtins.input", return_value="")
    def test_interactive_prompt_default_enter_key(self, mock_input):
        argv = ["main.py"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=True)
        self.assertEqual(choice, "tk")

    @patch("builtins.input", side_effect=EOFError)
    def test_interactive_prompt_eof_handling(self, mock_input):
        argv = ["main.py"]
        choice = select_ui_framework(argv=argv, env={}, is_interactive=True)
        self.assertEqual(choice, "tk")

    def test_frozen_executable_strictly_defaults_to_tk(self):
        """When running inside a frozen Arbor.exe, always return 'tk' with zero migration risk."""
        with patch.object(sys, "frozen", True, create=True):
            # Even if flags or env variables specify qt, frozen exe enforces stable Tkinter
            choice = select_ui_framework(argv=["main.py", "--ui", "qt"], env={"ARBOR_UI": "qt"}, is_interactive=True)
            self.assertEqual(choice, "tk")


if __name__ == "__main__":
    unittest.main()
