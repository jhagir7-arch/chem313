"""Contracts for the isolated extended-engine worker.

This module deliberately covers only bounded local calculations whose runtime
was exercised in ``.engines/extended`` on macOS arm64.  It does not imply that
the rest of the source catalog is installed or integrated.
"""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


Finite = Annotated[float, Field(allow_inf_nan=False, ge=-1_000_000, le=1_000_000)]
Coordinate = Annotated[list[Finite], Field(min_length=3, max_length=3)]


class Inputs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Geometry(Inputs):
    atomic_numbers: Annotated[list[Annotated[int, Field(ge=1, le=86)]], Field(min_length=2, max_length=20)]
    coordinates_angstrom: Annotated[list[Coordinate], Field(min_length=2, max_length=20)]
    charge: Annotated[int, Field(ge=-5, le=5)] = 0

    @model_validator(mode="after")
    def matching_coordinates(self):
        if len(self.atomic_numbers) != len(self.coordinates_angstrom):
            raise ValueError("atomic_numbers and coordinates_angstrom must have equal length")
        return self


class PySCFRHF(Geometry):
    basis: Annotated[str, Field(pattern=r"^(sto-3g|6-31g)$")] = "sto-3g"

    @model_validator(mode="after")
    def closed_shell_only(self):
        if (sum(self.atomic_numbers) - self.charge) % 2:
            raise ValueError("pyscf.rhf_singlepoint requires an even-electron closed-shell system")
        return self


class SpectrumPair(Inputs):
    reference_mz: Annotated[list[Finite], Field(min_length=1, max_length=500)]
    reference_intensities: Annotated[list[Finite], Field(min_length=1, max_length=500)]
    query_mz: Annotated[list[Finite], Field(min_length=1, max_length=500)]
    query_intensities: Annotated[list[Finite], Field(min_length=1, max_length=500)]
    tolerance_da: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] = 0.01

    @model_validator(mode="after")
    def valid_peaks(self):
        if len(self.reference_mz) != len(self.reference_intensities):
            raise ValueError("reference m/z and intensity lists must have equal length")
        if len(self.query_mz) != len(self.query_intensities):
            raise ValueError("query m/z and intensity lists must have equal length")
        if any(value <= 0 for value in self.reference_mz + self.query_mz):
            raise ValueError("m/z values must be positive")
        if any(value < 0 for value in self.reference_intensities + self.query_intensities):
            raise ValueError("intensities must be non-negative")
        return self


class MeekoPreparation(Inputs):
    smiles: Annotated[str, Field(min_length=1, max_length=500)]


OPERATIONS = {
    "pyscf.rhf_singlepoint": (
        "PySCF",
        PySCFRHF,
        "Run a bounded closed-shell RHF single-point calculation",
        "Coordinates angstrom; energy Hartree",
        "RHF only, STO-3G or 6-31G basis, no geometry optimization, solvation, excited states, or experimental validation.",
    ),
    "tblite.gfn2_singlepoint": (
        "tblite",
        Geometry,
        "Run a bounded GFN2-xTB single-point calculation",
        "Coordinates angstrom; energy Hartree; charges in elementary-charge units",
        "GFN2-xTB approximation only; no optimization, conformer search, solvation, property prediction, or experimental validation.",
    ),
    "matchms.cosine_greedy": (
        "matchms",
        SpectrumPair,
        "Compare two mass spectra with cosine greedy matching",
        "m/z and tolerance in Da; cosine score dimensionless",
        "Raw supplied peaks only: no peak cleaning, precursor filtering, library identification, retention-time matching, or chemical identity inference.",
    ),
    "meeko.prepare_pdbqt": (
        "Meeko",
        MeekoPreparation,
        "Generate one deterministic 3D PDBQT preparation from SMILES",
        "PDBQT coordinates Angstrom; partial charges are Meeko/RDKit preparation output",
        "One RDKit ETKDG/UFF conformer only; preparation does not establish docking pose, binding affinity, protonation state, or biological activity.",
    ),
}


# Small deterministic inputs used by the operation registry and runtime check.
# They are examples, not reference spectra, docking studies, or validation data.
EXAMPLES = {
    "pyscf.rhf_singlepoint": {
        "atomic_numbers": [1, 1],
        "coordinates_angstrom": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
        "charge": 0,
        "basis": "sto-3g",
    },
    "tblite.gfn2_singlepoint": {
        "atomic_numbers": [1, 1],
        "coordinates_angstrom": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]],
        "charge": 0,
    },
    "matchms.cosine_greedy": {
        "reference_mz": [100.0, 200.0],
        "reference_intensities": [1.0, 0.5],
        "query_mz": [100.005, 200.0],
        "query_intensities": [0.8, 0.5],
        "tolerance_da": 0.01,
    },
    "meeko.prepare_pdbqt": {"smiles": "CCO"},
}


def validate_operation(operation: str, inputs: object) -> dict:
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("Operation is not in the extended-engine allowlist")
    return OPERATIONS[operation][1].model_validate(inputs).model_dump()


def descriptions() -> list[dict]:
    return [
        dict(
            operation=key,
            engine=value[0],
            label=value[2],
            input_schema=value[1].model_json_schema(),
            example=EXAMPLES[key],
            units=value[3],
            limitations=value[4],
            effect="project_write",
            resources={
                "cpu_threads": 1,
                "wall_seconds": 120,
                "max_output_bytes": 1_000_000,
                "gpu": False,
                "memory": "Observed RSS recorded; no hardened memory sandbox",
            },
        )
        for key, value in OPERATIONS.items()
    ]
