"""The one place that says which molecules, force fields and parameter bounds the shell may offer.

The interface reads this through GET /api/catalog and must not carry its own copy. Validation in
conformers.py uses the same tables, so what the interface shows and what the engine accepts cannot
drift apart.
"""

CATALOG_SCHEMA = "chem313.catalog.v1"

# Beginner starters: small, neutral, MMFF94-covered, and quick. Order is the display order.
STARTERS = (
    {"id": "ethanol", "name": "Ethanol", "smiles": "CCO", "formula": "C2H6O"},
    {"id": "water", "name": "Water", "smiles": "O", "formula": "H2O"},
    {"id": "methane", "name": "Methane", "smiles": "C", "formula": "CH4"},
    {"id": "butane", "name": "Butane", "smiles": "CCCC", "formula": "C4H10"},
    {"id": "benzene", "name": "Benzene", "smiles": "c1ccccc1", "formula": "C6H6"},
    {"id": "acetic-acid", "name": "Acetic acid", "smiles": "CC(=O)O", "formula": "C2H4O2"},
)

# Availability depends on RDKit atom types and bonding, not just the elements present.
FORCE_FIELDS = {
    "MMFF94": {
        "label": "MMFF94",
        "note": "Merck molecular force field; parameter availability depends on the structure.",
    },
    "UFF": {
        "label": "UFF",
        "note": "Universal force field; parameter availability depends on the structure.",
    },
}

RELAXATION = {
    "action": "molecule.relax_geometry",
    "embedding": "ETKDGv3",
    "defaults": {"force_field": "MMFF94", "seed": 42, "max_iterations": 1000},
    "limits": {
        "seed": {"min": 0, "max": 2_147_483_647},
        "max_iterations": {"min": 1, "max": 10_000},
        "heavy_atoms": {"max": 100},
        "force_tolerance": 1e-4,
        "energy_tolerance": 1e-6,
    },
    "inputs": ("smiles", "molblock"),
    "scope": ("Local force-field shape relaxation of one isolated molecule. Not a quantum calculation, "
              "reaction prediction, experimental measurement, or proof of a global minimum."),
}


def catalog() -> dict:
    """What the interface may offer; served verbatim by /api/catalog."""
    return {
        "schema": CATALOG_SCHEMA,
        "molecules": [dict(m) for m in STARTERS],
        "relaxation": {
            **RELAXATION,
            "inputs": list(RELAXATION["inputs"]),
            "force_fields": [
                {"id": key, "label": spec["label"], "note": spec["note"], "elements": []}
                for key, spec in FORCE_FIELDS.items()
            ],
        },
    }


def starter_name(canonical_smiles: str) -> str | None:
    """Display name for a starter, matched on canonical SMILES; None for any other molecule."""
    for molecule in STARTERS:
        if molecule["smiles"] == canonical_smiles:
            return molecule["name"]
    return None
