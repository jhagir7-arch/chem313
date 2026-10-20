"""Capabilities shipped in a frozen standalone distribution.

Source installations retain their separately configured worker environments.
The bundled profile is build metadata, never user-supplied project input.
"""
import json
from pathlib import Path
import sys


def bundled_profile():
    if not getattr(sys, "frozen", False):
        return None
    path = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "bundle.json"
    if not path.is_file():
        return None  # legacy frozen distributions have separate workers
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "openchem.standalone.v1" or not isinstance(data.get("operations"), list):
        raise RuntimeError("Invalid standalone capability profile")
    return data


def bundled_manifest(profile):
    rows = []
    for entry in profile["engines"]:
        operations = entry["operations"]
        rows.append(dict(name=entry["name"], tier="core", domain=entry["domain"], registered=True,
                         source=dict(downloaded=False, repo=entry["repo"], commit=None),
                         runtime=dict(bundled=True, installed=True, loadable=True, compatible=True,
                                      tested=False, integrated=True, version=entry["version"], status="BUNDLED_CORE",
                                      detail="Included in this standalone app. Installation presence is not a live scientific validation."),
                         operations=operations, scientifically_validated=False,
                         license=dict(reported=entry["license"], status="NOTICES_INCLUDED")))
    return dict(schema="openchem.engine.registry.v1", engines=rows,
                counts={key: sum(bool(row["registered"] if key == "registered" else row["source"]["downloaded"] if key == "downloaded" else row["runtime"][key]) for row in rows)
                        for key in ("registered", "downloaded", "installed", "loadable", "compatible", "tested", "integrated")},
                provenance="Versions identify bundled release wheels and JavaScript assets. See licenses/standalone-core for notices and native-file inventory.",
                model="Qwen weights are not included; a separately configured local model is optional.")
