import os
import re

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename to ensure it is safe to write to the filesystem.
    Removes directory path components and non-alphanumeric/dot/dash characters.
    """
    # Force baseline name extraction to prevent path traversal (e.g. ../../../file)
    base = os.path.basename(filename)
    # Strip drive letter if Windows path traversal is attempted
    _, base = os.path.splitdrive(base)
    # Replace whitespace and invalid characters with underscores
    clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', base)
    # Ensure it's not empty
    if not clean or clean in ['.', '..']:
        clean = 'downloaded_file'
    return clean
