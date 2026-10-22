"""Pydantic 2 contracts for bounded local bioscience operations."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


FinitePositive = Annotated[float, Field(gt=0, le=1_000_000, allow_inf_nan=False)]
Unit = Annotated[str, Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9_./^-]+$")]


class Inputs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class EnzymeMLDocument(Inputs):
    name: Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[^\r\n]+$")]


class FirstOrderDecay(Inputs):
    initial_A: FinitePositive
    rate_per_time: FinitePositive
    times: Annotated[list[Annotated[float, Field(ge=0, le=1000, allow_inf_nan=False)]], Field(min_length=2, max_length=101)]
    time_unit: Unit
    rate_unit: Unit

    @model_validator(mode="after")
    def bounded_and_dimensionally_labeled(self):
        if self.times[0] != 0:
            raise ValueError("times must start at 0")
        if any(next_time < current for current, next_time in zip(self.times, self.times[1:])):
            raise ValueError("times must be sorted ascending")
        if self.rate_unit != f"1/{self.time_unit}":
            raise ValueError("rate_unit must be written as 1/<time_unit>")
        return self


OPERATIONS = {
    "pyenzyme.document": (
        "PyEnzyme",
        EnzymeMLDocument,
        "Construct a bounded EnzymeML document payload",
        "Metadata only; no measurement units are inferred",
        "Serialization only: no external identifiers, files, network fetches, biochemical validation, or publication.",
    ),
    "pysb.first_order_decay": (
        "PySB",
        FirstOrderDecay,
        "Solve a fixed first-order A-to-zero decay model",
        "Times use the supplied time_unit; rate uses explicit reciprocal rate_unit; A uses arbitrary supplied units",
        "Fixed A -> 0 model only; no arbitrary rules, model code, files, chemical kinetics validation, parameter fitting, or biological interpretation.",
    ),
}

EXAMPLES = {
    "pyenzyme.document": {"name": "Chem313 bioscience example"},
    "pysb.first_order_decay": {
        "initial_A": 1.0,
        "rate_per_time": 1.0,
        "times": [0.0, 1.0],
        "time_unit": "s",
        "rate_unit": "1/s",
    },
}


def validate_operation(operation: str, inputs: object) -> dict:
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("Operation is not in the bioscience allowlist")
    return OPERATIONS[operation][1].model_validate(inputs).model_dump()


def descriptions() -> list[dict]:
    return [
        dict(
            schema="openchem.capability.v1",
            operation=key,
            engine=value[0],
            label=value[2],
            input_schema=value[1].model_json_schema(),
            example=EXAMPLES[key],
            units=value[3],
            limitations=value[4],
            effect="project_write",
            input_formats=["JSON"],
            output_formats=["JSON"],
            source_preservation="Original approved JSON stored before execution; result and audit records stored separately",
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
