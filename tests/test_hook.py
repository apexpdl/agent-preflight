"""Tests for the import hook module."""

import sys
import pytest
from agent_preflight.hook import _PreflightFinder, install, uninstall


class TestImportHook:
    def test_install(self):
        # Ensure hook gets installed
        uninstall()
        assert install() is True
        found = any(isinstance(f, _PreflightFinder) for f in sys.meta_path)
        assert found

    def test_install_idempotent(self):
        uninstall()
        install()
        install()
        count = sum(1 for f in sys.meta_path if isinstance(f, _PreflightFinder))
        assert count == 1

    def test_uninstall(self):
        install()
        uninstall()
        found = any(isinstance(f, _PreflightFinder) for f in sys.meta_path)
        assert not found

    def test_finder_watches_openclaw(self):
        assert "openclaw" in _PreflightFinder._WATCHED

    def test_finder_ignores_unknown(self):
        finder = _PreflightFinder()
        assert finder.find_module("some_random_module") is None

    def test_reinstall_after_uninstall(self):
        uninstall()
        install()
        found = any(isinstance(f, _PreflightFinder) for f in sys.meta_path)
        assert found

    def teardown_method(self):
        # Clean up: re-install hook (it auto-installs on import)
        install()
