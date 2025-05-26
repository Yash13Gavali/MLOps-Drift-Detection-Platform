"""Verify interpreter, platform, and installed-distribution parity."""

import hashlib
import importlib.metadata
import json
import platform


def fingerprint() -> str:
    """Hash the complete installed package inventory and Python platform."""
    inventory = sorted((d.metadata["Name"].lower(), d.version) for d in importlib.metadata.distributions())
    payload = {"python": platform.python_version(), "system": platform.system(),
               "machine": platform.machine(), "packages": inventory}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

