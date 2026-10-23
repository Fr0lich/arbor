import unittest
from unittest.mock import patch, mock_open, MagicMock
import utils

class TestUtils(unittest.TestCase):
    def setUp(self):
        # Reset the global variable before each test
        utils._SESSION_HAS_ERRORS = False

    def test_session_had_errors_initially_false(self):
        self.assertFalse(utils.session_had_errors())

    @patch('utils.get_session_log_path')
    @patch('builtins.open', new_callable=mock_open)
    @patch('builtins.print')
    def test_debug_error_success(self, mock_print, mock_file, mock_get_path):
        mock_get_path.return_value = "mock_log_path.log"

        utils.debug_error("Test Context", "Extra Info")

        self.assertTrue(utils._SESSION_HAS_ERRORS)
        self.assertTrue(utils.session_had_errors())

        # Verify print was called
        self.assertTrue(mock_print.called)
        print_args = mock_print.call_args[0][0]
        self.assertIn("[ERROR] Test Context", print_args)
        self.assertIn("Extra Info", print_args)

        # Verify file was written
        mock_file.assert_called_once_with("mock_log_path.log", "a", encoding="utf-8")
        handle = mock_file()
        self.assertTrue(handle.write.called)
        write_args = handle.write.call_args[0][0]
        self.assertIn("[ERROR] Test Context", write_args)
        self.assertIn("Extra Info", write_args)

    @patch('utils.get_session_log_path')
    @patch('builtins.open')
    @patch('builtins.print')
    def test_debug_error_file_io_exception(self, mock_print, mock_file, mock_get_path):
        mock_get_path.return_value = "mock_log_path.log"

        # Mock file open to raise an exception
        mock_file.side_effect = IOError("Mocked IO Error")

        # This should not raise an exception
        utils.debug_error("Test Context")

        self.assertTrue(utils._SESSION_HAS_ERRORS)

        # Verify print was still called
        self.assertTrue(mock_print.called)
        print_args = mock_print.call_args[0][0]
        self.assertIn("[ERROR] Test Context", print_args)

if __name__ == '__main__':
    unittest.main()
