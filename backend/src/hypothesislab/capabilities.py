"""Versioned capability declaration for local clients.

The manifest describes this core engine only.  Desktop-native extensions report
their live host status through their own actions rather than inheriting claims.
"""
from __future__ import annotations

from . import __version__
from .chemistry import HAS_RDKIT, RDKIT_VERSION
from .validation import ALLOWED

CONTRACT_VERSION = "openchem.capabilities.v1"


def manifest() -> dict:
    actions = [
        {
            "action": name,
            "effect": effect,
            "protocol": "hypothesislab.request.v2",
            "approval": "single-use-SQLite-ticket" if effect != "read_only" else "explicit-apply",
            "evidence": "LOCAL_CORE_TESTED" if name != "avogadro.ping" else "TRANSPORT_PROBE_ONLY",
            "native_host_tested": False,
        }
        for name, (_, effect) in sorted(ALLOWED.items())
    ]
    return {
        "contract_version": CONTRACT_VERSION,
        "backend": "hypothesislab-local-core",
        "backend_version": __version__,
        "source_data_policy": "immutable-originals; normalized-derivatives-separate; unsigned-local-events; reaction-ket-rejected-on-single-mol-endpoints (E-015)",
        "rdkit_version": RDKIT_VERSION,
        "rdkit_available": HAS_RDKIT,
        "actions": actions,
        "optional_hosts": [{"host": "Avogadro 2", "status": "RUNTIME_STATUS_REQUIRED"}],
        "safety": {"local_single_user_only": True, "authenticated_remote_access": False, "scientific_novelty_demonstrated": False},
    }
