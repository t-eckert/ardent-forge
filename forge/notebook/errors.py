class NotebookWriteError(Exception):
    """Raised when a notebook write is rejected (bad path, outside allowlist)."""
