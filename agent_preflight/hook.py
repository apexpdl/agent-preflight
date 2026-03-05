"""
Preflight import hook — automatic zero-config activation.

When this module is loaded (via sitecustomize, .pth file, or PYTHONSTARTUP),
it installs a lightweight import hook that watches for supported agent
frameworks. When a framework is imported, Preflight wraps it automatically.

No code changes. No decorators. No config files.

Activation methods (pick one):
    1. Environment variable:   PREFLIGHT_AUTO=1 python my_agent.py
    2. .pth file:              echo "import agent_preflight.hook" > preflight.pth
    3. Explicit import:        import agent_preflight.hook
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys
import threading
from typing import Optional

_installed = False
_lock = threading.Lock()


class _PreflightFinder(importlib.abc.MetaPathFinder):
    """Watches for agent framework imports and patches them post-load.

    This is NOT fragile monkeypatching. It uses Python's official
    import hook system (PEP 302 / PEP 451) to get notified when
    specific modules are imported, then wraps their public APIs
    through documented extension points.
    """

    _WATCHED = frozenset({
        "openclaw",
    })

    _patched: set[str] = set()

    def find_module(self, fullname: str, path=None):
        # Only intercept top-level framework imports we haven't patched yet
        if fullname in self._WATCHED and fullname not in self._patched:
            return self
        return None

    def load_module(self, fullname: str):
        # Let the real importer handle it first
        self._patched.add(fullname)
        if fullname in sys.modules:
            module = sys.modules[fullname]
        else:
            module = importlib.import_module(fullname)

        # Now wrap it
        _patch_framework(fullname, module)
        return module


def _patch_framework(name: str, module) -> None:
    """Apply Preflight wrapping to a loaded framework module."""
    if name == "openclaw":
        _patch_openclaw(module)


def _patch_openclaw(module) -> None:
    """Wrap OpenClaw's Agent class so all tool executions go through Preflight."""
    from agent_preflight.integrations.openclaw import enable_preflight

    pf = enable_preflight(silent=True)

    if hasattr(module, "Agent"):
        _original_init = module.Agent.__init__

        def _safe_init(self, *args, **kwargs):
            _original_init(self, *args, **kwargs)
            # Wrap known executor patterns
            for attr in ("execute_tool", "_execute", "run_tool"):
                if hasattr(self, attr):
                    setattr(self, attr, pf.wrap_sync_executor(getattr(self, attr)))
            for attr in ("async_execute_tool", "_async_execute", "arun_tool"):
                if hasattr(self, attr):
                    setattr(self, attr, pf.wrap_executor(getattr(self, attr)))

        module.Agent.__init__ = _safe_init


def install() -> bool:
    """Install the Preflight import hook.

    Safe to call multiple times — only installs once.
    Thread-safe.

    Returns True if the hook was installed (or was already installed).
    """
    global _installed
    with _lock:
        if _installed:
            return True

        # Don't double-install
        for finder in sys.meta_path:
            if isinstance(finder, _PreflightFinder):
                _installed = True
                return True

        sys.meta_path.insert(0, _PreflightFinder())
        _installed = True

        # Patch any frameworks that were already imported before the hook
        for name in _PreflightFinder._WATCHED:
            if name in sys.modules and name not in _PreflightFinder._patched:
                _PreflightFinder._patched.add(name)
                _patch_framework(name, sys.modules[name])

        return True


def uninstall() -> None:
    """Remove the Preflight import hook."""
    global _installed
    with _lock:
        sys.meta_path[:] = [
            f for f in sys.meta_path if not isinstance(f, _PreflightFinder)
        ]
        _installed = False
        _PreflightFinder._patched.clear()


# Auto-install on import
install()
