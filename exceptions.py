"""
Custom exception classes for Arbor to provide more descriptive error handling
and prevent the swallowing of generic exceptions.
"""

class ArborError(Exception):
    """Base class for exceptions in this application."""
    pass

class DatabaseLoadError(ArborError):
    """Exception raised when there is an error loading or connecting to the database."""
    def __init__(self, message="Failed to load database.", filepath=None):
        self.filepath = filepath
        super().__init__(f"{message} (File: {filepath})" if filepath else message)

class UIConfigurationError(ArborError):
    """Exception raised when there is an error parsing or applying UI configurations."""
    def __init__(self, message="Invalid UI configuration."):
        super().__init__(message)

class ImageLoadError(ArborError):
    """Exception raised when an image fails to load or process."""
    def __init__(self, message="Failed to load image.", filepath=None):
        self.filepath = filepath
        super().__init__(f"{message} (File: {filepath})" if filepath else message)
