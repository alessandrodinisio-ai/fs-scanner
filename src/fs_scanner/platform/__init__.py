"""Platform abstraction layer.

Auto-detects the current OS and exports the appropriate platform module.
"""

import sys

if sys.platform == "darwin":
    from .macos import MacOSPlatform as _Platform
else:
    # Fallback: use base (cross-platform only, no OS-specific suggestions)
    from .base import BasePlatform as _Platform

current = _Platform()
