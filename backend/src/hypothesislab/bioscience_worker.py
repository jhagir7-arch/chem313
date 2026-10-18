"""Standalone bounded worker for the exercised bioscience probe environment.

It intentionally does not import ``bioscience_contracts`` because the probe
environment resolves PyEnzyme against Pydantic 1 while registry contracts use
Pydantic 2. The same narrow envelope and input rules are implemented here.
"""
from __future__ import annotations

import contextlib
import importlib.util
import importlib.metadata as metadata
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time


for _thread_limit in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_thread_limit] = "1"


OPERATION_METADATA = {
    "pyenzyme.document": (
        "PyEnzyme", "pyenzyme", "Metadata only; no measurement units are inferred",
        "Serialization only: no external identifiers, files, network fetches, biochemical validation, or publication.",
    ),
    "pysb.first_order_decay": (
        "PySB", "pysb",
        "Times use the supplied time_unit; rate uses explicit reciprocal rate_unit; A uses arbitrary supplied units",
        "Fixed A -> 0 model only; no arbitrary rules, model code, files, chemical kinetics validation, parameter fitting, or biological interpretation.",
    ),
}


def _finite_number(value: object, field: str, *, positive: bool = False, maximum: float = 1_000_000) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a JSON number")
    number = float(value)
    if not math.isfinite(number) or (number <= 0 if positive else number < 0) or number > maximum:
        comparison = "positive and finite" if positive else "finite and non-negative"
        raise ValueError(f"{field} must be {comparison} and at most {maximum}")
    return number


def _unit(value: object, field: str) -> str:
    if not isinstance(value, str) or not (1 <= len(value) <= 24):
        raise ValueError(f"{field} must be a 1-24 character unit label")
    if not all(character.isalnum() or character in "_./^-" for character in value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def validate_request(request: object) -> tuple[str, dict]:
    if not isinstance(request, dict) or set(request) != {"operation", "inputs"}:
        raise ValueError("Request must contain only operation and inputs")
    operation, inputs = request["operation"], request["inputs"]
    if not isinstance(operation, str) or operation not in OPERATION_METADATA:
        raise ValueError("Operation is not in the bioscience allowlist")
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be an object")
    if operation == "pyenzyme.document":
        if set(inputs) != {"name"}:
            raise ValueError("pyenzyme.document inputs must contain only name")
        name = inputs["name"]
        if not isinstance(name, str) or not (1 <= len(name) <= 120) or "\n" in name or "\r" in name:
            raise ValueError("name must be a one-line string of 1-120 characters")
        return operation, {"name": name}
    expected = {"initial_A", "rate_per_time", "times", "time_unit", "rate_unit"}
    if set(inputs) != expected:
        raise ValueError("pysb.first_order_decay inputs contain unsupported or missing fields")
    times = inputs["times"]
    if not isinstance(times, list) or not (2 <= len(times) <= 101):
        raise ValueError("times must contain 2-101 values")
    checked_times = [_finite_number(value, "times[]", maximum=1000) for value in times]
    if checked_times[0] != 0 or any(next_time < current for current, next_time in zip(checked_times, checked_times[1:])):
        raise ValueError("times must be sorted and start at 0")
    time_unit = _unit(inputs["time_unit"], "time_unit")
    rate_unit = _unit(inputs["rate_unit"], "rate_unit")
    if rate_unit != f"1/{time_unit}":
        raise ValueError("rate_unit must be written as 1/<time_unit>")
    return operation, {
        "initial_A": _finite_number(inputs["initial_A"], "initial_A", positive=True),
        "rate_per_time": _finite_number(inputs["rate_per_time"], "rate_per_time", positive=True),
        "times": checked_times,
        "time_unit": time_unit,
        "rate_unit": rate_unit,
    }


def run(operation: str, inputs: dict) -> dict:
    if operation == "pyenzyme.document":
        from pyenzyme import EnzymeMLDocument

        document = EnzymeMLDocument(name=inputs["name"])
        payload = document.dict()
        return {"name": payload["name"], "level": payload["level"], "version": payload["version"], "method": "EnzymeMLDocument"}
    if operation == "pysb.first_order_decay":
        from pysb import Initial, Model, Monomer, Observable, Parameter, Rule
        from pysb.integrate import odesolve

        frozen_root = getattr(sys, "_MEIPASS", None)
        if frozen_root:
            bngpath = Path(frozen_root) / "bionetgen" / "bng-mac"
        else:
            bionetgen_spec = importlib.util.find_spec("bionetgen")
            if bionetgen_spec is None or bionetgen_spec.origin is None:
                raise RuntimeError("BioNetGen package is unavailable")
            bngpath = Path(bionetgen_spec.origin).resolve().parent / "bng-mac"
        if not (bngpath / "BNG2.pl").is_file():
            raise RuntimeError("Bundled macOS BioNetGen runtime is unavailable")
        os.environ["BNGPATH"] = str(bngpath)
        model = Model()
        species = Monomer("A")
        rate = Parameter("k", inputs["rate_per_time"])
        initial = Parameter("a0", inputs["initial_A"])
        Initial(species(), initial)
        Rule("decay", species() >> None, rate)
        Observable("A_total", species())
        solution = odesolve(model, inputs["times"], compiler="python")
        return {
            "A": [float(value) for value in solution["A_total"]],
            "times": inputs["times"],
            "initial_A": inputs["initial_A"],
            "rate_per_time": inputs["rate_per_time"],
            "time_unit": inputs["time_unit"],
            "rate_unit": inputs["rate_unit"],
            "method": "PySB fixed first-order decay via bundled BioNetGen",
            "dependencies": {"bionetgen": metadata.version("bionetgen")},
        }
    raise ValueError("Unimplemented operation")


def _wall_timeout(_signal: int, _frame: object) -> None:
    raise TimeoutError("Worker exceeded 120 second wall limit")


def main() -> None:
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU, (110, 110))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_500_000, 1_500_000))
    signal.signal(signal.SIGALRM, _wall_timeout)
    signal.alarm(120)
    try:
        raw = sys.stdin.buffer.read(250_001)
        if len(raw) > 250_000:
            raise ValueError("Input exceeds 250 KB")
        operation, inputs = validate_request(json.loads(raw))
        with contextlib.redirect_stdout(sys.stderr):
            output = run(operation, inputs)
        engine, distribution, units, limitations = OPERATION_METADATA[operation]
        version: object = metadata.version(distribution)
        result = {
            "schema": "openchem.science.result.v1",
            "operation": operation,
            "engine": engine,
            "version": version,
            "output": output,
            "units": units,
            "limitations": limitations,
            "resources": {
                "wall_seconds": time.monotonic() - started,
                "wall_limit_seconds": 120,
                "user_cpu_seconds": resource.getrusage(resource.RUSAGE_SELF).ru_utime,
                "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "gpu": False,
                "threads": 1,
            },
        }
        encoded = json.dumps(result, allow_nan=False)
        if len(encoded.encode("utf-8")) > 1_000_000:
            raise ValueError("Result exceeds 1 MB cap")
        print(encoded)
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}))
        raise SystemExit(2)
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
