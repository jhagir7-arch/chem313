"""Single allow-listed action envelope for CLI, HTTP and future native clients."""
from __future__ import annotations
import re
from typing import Any

PROJECT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")
ALLOWED = {
    "molecule.inspect_smiles": ("smiles", "read_only"),
    "molecule.import_molfile": ("molfile", "project_write"),
    "molecule.fidelity_audit": ("molfile", "read_only"),
    "avogadro.ping": (None, "external_read_only"),
    "measurement.fit_csv": ("csv", "project_write"),
}

class InputError(ValueError):
    pass


def validate(action: str, params: dict[str, Any], project: str) -> str:
    if not isinstance(action, str) or action not in ALLOWED:
        raise InputError("Unknown action; available actions are explicit and versioned")
    if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
        raise InputError("Invalid project identifier")
    if not isinstance(params, dict):
        raise InputError("Parameters must be a JSON object")
    required, effect = ALLOWED[action]
    expected = {"csv", "x_column", "y_column", "x_unit", "y_unit"} if action == "measurement.fit_csv" else ({required} if required else set())
    if set(params) != expected:
        raise InputError("Unexpected/missing parameters for " + action)
    if required:
        value = params[required]
        if not isinstance(value, str) or not value.strip():
            raise InputError(required + " must be a nonempty string")
        if len(value.encode("utf-8")) > (250_000 if required in ("molfile", "csv") else 5_000):
            raise InputError("Input exceeds the fixed size cap")
    if action == "measurement.fit_csv":
        for key in ("x_column", "y_column", "x_unit", "y_unit"):
            if (not isinstance(params[key], str) or not (0 < len(params[key]) <= 64)
                    or not params[key].strip()):
                raise InputError(f"{key} must have length 1..64")
    return effect
