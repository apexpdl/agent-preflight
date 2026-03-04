"""
Federated Global Signal Network — optional privacy-preserving
intelligence sharing between ATF instances.

This is a stub interface for future implementation. When enabled,
ATF instances can share anonymized action fingerprints and receive
global stability signals without exposing raw payloads.
"""

from agent_preflight.federation.protocol import (
    FederatedSignal,
    GlobalStabilitySignal,
)
from agent_preflight.federation.client import FederationClient

__all__ = ["FederatedSignal", "GlobalStabilitySignal", "FederationClient"]
