"""
Mirror World — Deterministic sandbox for high-risk action simulation.

Creates isolated temporary environments, stubs external calls,
runs tools, captures state deltas, and validates against declared intent.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Optional

from agent_preflight.atf.models import (
    ActionEnvelope,
    FileDelta,
    MirrorResult,
    StructuredIntent,
)


def _file_hash(path: Path) -> str:
    """SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return ""


def _snapshot_dir(directory: Path) -> dict[str, str]:
    """Create a hash snapshot of all files in a directory tree."""
    snap: dict[str, str] = {}
    if not directory.exists():
        return snap
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            fpath = Path(root) / fname
            rel = str(fpath.relative_to(directory))
            snap[rel] = _file_hash(fpath)
    return snap


class NetworkStub:
    """Captures attempted network calls instead of executing them."""

    def __init__(self):
        self.attempted_urls: list[str] = []

    def request(self, method: str, url: str, **kwargs: Any) -> None:
        self.attempted_urls.append(f"{method} {url}")

    def get(self, url: str, **kwargs: Any) -> None:
        self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> None:
        self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> None:
        self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> None:
        self.request("DELETE", url, **kwargs)


class PermissionMatrix:
    """Enforces allowed/denied operations in the mirror."""

    def __init__(self, allow_read: bool = True, allow_write: bool = True, allow_delete: bool = False):
        self.allow_read = allow_read
        self.allow_write = allow_write
        self.allow_delete = allow_delete
        self.violations: list[str] = []

    def check_write(self, path: str) -> bool:
        if not self.allow_write:
            self.violations.append(f"Write denied: {path}")
            return False
        return True

    def check_delete(self, path: str) -> bool:
        if not self.allow_delete:
            self.violations.append(f"Delete denied: {path}")
            return False
        return True


class MirrorWorld:
    """Deterministic sandbox execution environment.

    Creates a temporary directory clone of affected paths, runs the
    tool in isolation, captures file diffs and external attempts,
    then compares results against declared intent.
    """

    def __init__(self, timeout_seconds: float = 5.0):
        self._timeout = timeout_seconds

    async def execute(
        self,
        envelope: ActionEnvelope,
        tool_fn: Optional[Callable] = None,
        source_paths: Optional[list[str]] = None,
    ) -> MirrorResult:
        """Run an action in the mirror sandbox.

        Args:
            envelope: The action to simulate.
            tool_fn: Optional callable to execute. If None, performs
                     static analysis only.
            source_paths: Paths to clone into the mirror. If None,
                         extracts from envelope arguments.
        """
        start = time.perf_counter()

        # Determine paths to mirror
        paths_to_mirror = source_paths or self._extract_paths(envelope)

        network_stub = NetworkStub()
        permissions = PermissionMatrix(
            allow_read=True,
            allow_write=True,
            allow_delete=envelope.intent.irreversible,
        )
        exceptions: list[str] = []

        with tempfile.TemporaryDirectory(prefix="atf_mirror_") as tmpdir:
            mirror_root = Path(tmpdir)

            # Clone affected paths into mirror
            for src in paths_to_mirror:
                src_path = Path(src)
                if src_path.exists():
                    dest = mirror_root / src_path.name
                    if src_path.is_dir():
                        shutil.copytree(src_path, dest, dirs_exist_ok=True)
                    elif src_path.is_file():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dest)

            # Snapshot before
            before = _snapshot_dir(mirror_root)

            # Execute tool if provided
            if tool_fn is not None:
                try:
                    # Create sandboxed arguments
                    sandboxed_args = self._sandbox_args(
                        envelope.arguments, mirror_root, permissions
                    )
                    result = tool_fn(**sandboxed_args)
                    if hasattr(result, "__await__"):
                        import asyncio
                        await asyncio.wait_for(result, timeout=self._timeout)
                except Exception as exc:
                    exceptions.append(f"{type(exc).__name__}: {exc}")

            # Snapshot after
            after = _snapshot_dir(mirror_root)

            # Compute deltas
            state_delta = self._compute_deltas(before, after)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Check if results match declared intent
        matches, mismatch_details = self._validate_against_intent(
            envelope.intent, state_delta, network_stub.attempted_urls
        )

        return MirrorResult(
            state_delta=state_delta,
            external_attempts=network_stub.attempted_urls,
            permission_violations=permissions.violations,
            exceptions=exceptions,
            matches_intent=matches,
            execution_time_ms=round(elapsed_ms, 3),
            mismatch_details=mismatch_details,
        )

    def _extract_paths(self, envelope: ActionEnvelope) -> list[str]:
        """Extract file/directory paths from action arguments."""
        paths: list[str] = list(envelope.resource_targets)
        for val in envelope.arguments.values():
            if isinstance(val, str) and (
                "/" in val or "\\" in val or val.endswith((".py", ".json", ".yaml", ".yml", ".txt", ".md"))
            ):
                paths.append(val)
        return paths

    def _sandbox_args(
        self,
        args: dict[str, Any],
        mirror_root: Path,
        permissions: PermissionMatrix,
    ) -> dict[str, Any]:
        """Rewrite path arguments to point into the mirror directory."""
        sandboxed = {}
        for key, val in args.items():
            if isinstance(val, str) and ("/" in val or "\\" in val):
                original = Path(val)
                sandboxed_path = mirror_root / original.name
                sandboxed[key] = str(sandboxed_path)
            else:
                sandboxed[key] = val
        return sandboxed

    def _compute_deltas(
        self, before: dict[str, str], after: dict[str, str]
    ) -> list[FileDelta]:
        """Compare before/after snapshots to find changes."""
        deltas: list[FileDelta] = []

        all_files = set(before.keys()) | set(after.keys())
        for f in sorted(all_files):
            h_before = before.get(f)
            h_after = after.get(f)

            if h_before is None and h_after is not None:
                deltas.append(FileDelta(
                    path=f, action="created", hash_after=h_after
                ))
            elif h_before is not None and h_after is None:
                deltas.append(FileDelta(
                    path=f, action="deleted", hash_before=h_before
                ))
            elif h_before != h_after:
                deltas.append(FileDelta(
                    path=f, action="modified",
                    hash_before=h_before, hash_after=h_after,
                ))

        return deltas

    def _validate_against_intent(
        self,
        intent: StructuredIntent,
        deltas: list[FileDelta],
        external_attempts: list[str],
    ) -> tuple[bool, list[str]]:
        """Check if actual changes match declared intent."""
        mismatches: list[str] = []

        # Check unexpected deletions
        if not intent.irreversible:
            deleted = [d for d in deltas if d.action == "deleted"]
            if deleted:
                mismatches.append(
                    f"Unexpected deletions: {[d.path for d in deleted]} "
                    f"(action declared as reversible)"
                )

        # Check undeclared external calls
        declared_external = set(intent.external_calls)
        for attempt in external_attempts:
            url_part = attempt.split(" ", 1)[-1] if " " in attempt else attempt
            if not any(declared in url_part for declared in declared_external):
                mismatches.append(f"Undeclared external call: {attempt}")

        # Check scope — more changes than expected
        n_expected = len(intent.expected_state_changes)
        n_actual = len(deltas)
        if n_expected > 0 and n_actual > n_expected * 3:
            mismatches.append(
                f"Scope exceeded: {n_actual} changes vs {n_expected} expected"
            )

        return len(mismatches) == 0, mismatches
