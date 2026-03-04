"""
Federation Client — stub implementation for the global signal network.

Currently returns neutral signals. When a federation server is deployed,
this client will communicate via HTTPS with anonymized metadata only.
"""

from __future__ import annotations

from typing import Optional

from agent_preflight.federation.protocol import FederatedSignal, GlobalStabilitySignal


class FederationClient:
    """Client for the federated global signal network.

    Stub implementation — returns neutral signals.
    Replace with HTTP client when federation server is available.
    """

    def __init__(self, endpoint: Optional[str] = None, instance_id: str = ""):
        self._endpoint = endpoint
        self._instance_id = instance_id
        self._enabled = endpoint is not None

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def report_signal(self, signal: FederatedSignal) -> bool:
        """Report an action signal to the federation network.

        Returns True if successfully reported.
        """
        if not self._enabled:
            return False
        # Stub: in production, POST to self._endpoint
        return True

    async def query_stability(self, action_fingerprint: str) -> GlobalStabilitySignal:
        """Query global stability for an action fingerprint.

        Returns neutral signal when federation is not connected.
        """
        if not self._enabled:
            return GlobalStabilitySignal(
                action_fingerprint=action_fingerprint,
                global_failure_rate=0.0,
                emerging_risk_flag=False,
                volatility_trend="stable",
                sample_size=0,
            )
        # Stub: in production, GET from self._endpoint
        return GlobalStabilitySignal(
            action_fingerprint=action_fingerprint,
            global_failure_rate=0.0,
            emerging_risk_flag=False,
            volatility_trend="stable",
            sample_size=0,
        )
