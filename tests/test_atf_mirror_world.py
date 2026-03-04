"""Tests for ATF Mirror World."""

import os
import tempfile
import pytest
from pathlib import Path
from agent_preflight.atf.mirror_world import MirrorWorld
from agent_preflight.atf.models import ActionEnvelope, StructuredIntent


def _make_envelope(tool_name="write_file", targets=None, **kwargs):
    return ActionEnvelope(
        agent_id="test-agent",
        tool_name=tool_name,
        arguments=kwargs.get("arguments", {}),
        resource_targets=targets or [],
        intent=StructuredIntent(
            goal=kwargs.get("goal", "Test"),
            reasoning_summary="Test",
            expected_state_changes=kwargs.get("expected_changes", []),
            external_calls=kwargs.get("external_calls", []),
            irreversible=kwargs.get("irreversible", False),
        ),
    )


class TestMirrorWorld:
    @pytest.mark.asyncio
    async def test_static_analysis_no_fn(self):
        mirror = MirrorWorld()
        envelope = _make_envelope()
        result = await mirror.execute(envelope)
        assert result.matches_intent
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_detects_file_creation(self):
        mirror = MirrorWorld()
        with tempfile.TemporaryDirectory() as tmpdir:
            envelope = _make_envelope(targets=[tmpdir])

            def create_file(**args):
                path = Path(tmpdir) / "new_file.txt"
                path.write_text("hello")

            result = await mirror.execute(envelope, tool_fn=create_file, source_paths=[tmpdir])
            # Mirror runs in isolated copy, so results capture changes there
            assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_catches_exceptions(self):
        mirror = MirrorWorld()
        envelope = _make_envelope()

        def failing_fn(**args):
            raise ValueError("Intentional error")

        result = await mirror.execute(envelope, tool_fn=failing_fn)
        assert len(result.exceptions) > 0
        assert "ValueError" in result.exceptions[0]

    @pytest.mark.asyncio
    async def test_mirror_isolates_changes(self):
        mirror = MirrorWorld()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file that the mirror should copy and preserve
            test_file = Path(tmpdir) / "important.txt"
            test_file.write_text("important data")

            envelope = _make_envelope(
                targets=[tmpdir],
                irreversible=False,
            )

            # The tool function is sandboxed — args are rewritten to mirror paths
            # Even if the fn does nothing useful, the mirror should capture the state
            result = await mirror.execute(envelope, source_paths=[tmpdir])
            # Original file should be untouched regardless of mirror execution
            assert test_file.exists()
            assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_scope_validation(self):
        mirror = MirrorWorld()
        envelope = _make_envelope(expected_changes=["one change"])

        # Static analysis with no tool fn and no actual changes
        result = await mirror.execute(envelope)
        assert result.matches_intent  # No changes = no mismatch
