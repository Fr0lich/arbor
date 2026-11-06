import os
import sys
import pytest
import utils


def test_debug_log_and_debug_error(tmp_path):
    # Verify session log path is created
    log_path = utils.get_session_log_path()
    assert log_path is not None
    assert os.path.exists(os.path.dirname(log_path))

    # Test debug_log
    utils.debug_log("INFO", "Diagnostic test message", "extra detail")
    
    # Test debug_error without exception
    initial_has_errors = utils.session_had_errors()
    utils.debug_error("Non-fatal context error", "extra detail", is_crash=False)
    assert utils.session_had_errors() is True

    # Test debug_error with exception context
    try:
        raise ValueError("Simulated diagnostic exception")
    except ValueError:
        utils.debug_error("Caught diagnostic exception", "extra info", is_crash=True)

    # Check file exists and contains message
    assert os.path.exists(log_path)
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "Diagnostic test message" in content
    assert "Non-fatal context error" in content
    assert "Caught diagnostic exception" in content
    assert "ValueError: Simulated diagnostic exception" in content


def test_legacy_stubs_compatibility():
    # Verify legacy queue stubs do not crash callers
    assert hasattr(utils, "_ensure_flush_thread")
    utils._ensure_flush_thread()

    assert hasattr(utils, "_flush_loop")
    utils._flush_loop()

    assert hasattr(utils, "_flush_log_queue")
    utils._flush_log_queue()

    assert hasattr(utils, "_log_queue")
