"""The 54-entry inventory joined with separately identified runtime evidence.

Downloaded upstream commit archives are not the source revision of installed
release wheels. Keeping both identities prevents a misleading pin claim.
"""
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from .science_jobs import operation_descriptions, worker_command


def _public_core_catalog():
    """Small source-mode catalog; no downloaded commit or binary claims."""
    rows = []
    for name, tier, domain, interface, license_name, repo, module, executable in [
        ("RDKit", "core", "cheminformatics", "python_cpp", "BSD-3-Clause", "https://github.com/rdkit/rdkit", "rdkit", None),
        ("Ketcher", "core", "molecular_editing", "browser_editor", "Apache-2.0", "https://github.com/epam/ketcher", None, None),
        ("3DmolJS", "extended", "molecular_visualization", "javascript_browser", "BSD-family", "https://github.com/3dmol/3Dmol.js", None, None),
        ("AvogadroApp", "core", "molecular_3d", "native_app", "BSD-family", "https://github.com/OpenChemistry/avogadroapp", None, "avogadro2"),
        ("OpenBabel", "core", "format_conversion", "native_cli", "GPL-2.0-family", "https://github.com/openbabel/openbabel", None, "obabel"),
    ]:
        rows.append({"name": name, "tier": tier, "domain": domain,
                     "source_repo_url": repo, "pinned_commit_sha": None,
                     "license_reported_unverified": license_name,
                     "interface_class": interface, "python_module": module,
                     "executable": executable, "source_archive_url": None,
                     "native_host_or_gpu_limit": "source-mode runtime must be installed and checked separately"})
    return {"engines": rows}


def _frontend_asset_present(name):
    root = Path(__file__).resolve().parents[3]
    dist = root / "frontend" / "dist"
    if name == "Ketcher":
        return any(dist.glob("**/*ketcher*"))
    if name == "3DmolJS":
        return any("3dmol" in p.name.lower() for p in dist.glob("assets/*.js"))
    return False


def _avogadro_runtime():
    from .avogadro_host import AvogadroHost
    root = Path(os.environ.get("OPENCHEM_DATA", Path.home() / "Library/Application Support/OpenChem"))
    return AvogadroHost(root).status()


def _runtime_present(name):
    if name == "RDKit":
        return importlib.util.find_spec("rdkit") is not None
    if name in {"Ketcher", "3DmolJS"}:
        return _frontend_asset_present(name)
    if name == "AvogadroApp":
        return bool(_avogadro_runtime().get("installed"))
    if name == "OpenBabel":
        return bool(shutil.which("obabel"))
    return False


def data_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3])) / "registry"


def read(name, default):
    root = data_root()
    if not root.is_dir() and not getattr(sys, "frozen", False):
        root = Path(__file__).resolve().parents[3] / "sources"
    path = root / name
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def evidence_file(name, default):
    result = read(name, None)
    if result is None and not getattr(sys, "frozen", False):
        filename = "extended_engine_feasibility_2026-10-17.json" if name == "feasibility.json" else name
        try:
            result = json.loads((Path(__file__).resolve().parents[3] / "evidence" / filename).read_text())
        except (OSError, ValueError):
            pass
    return default if result is None else result


def pending_runtime(entry, probe):
    """Describe the tested install route without declaring a platform impossible."""
    wheel = probe.get("wheel_dry_run", {})
    status = "SOURCE_ONLY"
    detail = "Pinned source preserved; native build and a typed executable adapter remain unimplemented."
    if wheel.get("status") == "WHEEL_RESOLVABLE":
        status = "NOT_INSTALLED"
        detail = "Binary dependency resolution succeeded on this Mac; installation, scientific adapter and reference checks remain pending. No platform blocker is established."
    elif wheel.get("status") == "NO_BINARY_WHEEL_OR_UNRESOLVABLE":
        status = "BINARY_INSTALL_ROUTE_BLOCKED"
        detail = "The isolated Python 3.12 binary-only install route failed. A separate package manager or source build is not yet tested. " + wheel.get("detail", "")[-2000:]
    elif probe.get("executable_probe", {}).get("status") == "UNAVAILABLE":
        status = "EXECUTABLE_MISSING"
        detail = probe["executable_probe"].get("error", "Executable unavailable") + "; a native build/install and typed CLI adapter remain pending."
    if entry["name"] == "PySB":
        status = "WORKER_UNAVAILABLE"
        detail = "The separate bioscience environment resolved BioNetGen and ran the fixed decay reference. This runtime still requires the verified bioscience worker; the earlier missing-dependency probe is historical."
    return dict(installed=False, loadable=False, compatible=False, tested=False, integrated=False,
                version=None, status=status, detail=detail,
                development_probe=probe, bundled=False)


def manifest():
    from .runtime_profile import bundled_profile, bundled_manifest
    profile = bundled_profile()
    if profile:
        return bundled_manifest(profile)
    catalog = read("ENGINE_CATALOG.json", None)
    if catalog is None:
        catalog = read("registry/ENGINE_CATALOG.json", _public_core_catalog())
    receipt = read("ACQUISITION_RECEIPT_2026-10-17.json", {})
    downloaded = {row["name"]: row for row in receipt.get("results", [])}
    results = {}
    for name in ("science-runtime.json", "extended-runtime.json", "bioscience-runtime.json"):
        evidence = read(name, {})
        if not evidence and not getattr(sys, "frozen", False):
            try:
                evidence = json.loads((Path(__file__).resolve().parents[3] / "evidence" / name).read_text())
            except (OSError, ValueError):
                evidence = {}
        for row in evidence.get("results", []):
            results[row["engine"]] = dict(row, checked_utc=evidence.get("generated_utc"))
    probes = {x["name"]: x for x in evidence_file("feasibility.json", {}).get("results", [])}
    operations = operation_descriptions()
    rows = []
    existing = {
        "RDKit": ("rdkit", "molecule.inspect_smiles, molecule.import_molfile, molecule.fidelity_audit, molecule.generate_conformer", "Core structure/conformer checks"),
        "Ketcher": ("3.18.0", "local molecule drawing and MOL editing", "Real browser editor checks; full reaction support not established"),
        "3DmolJS": ("2.5.5", "local molecular WebGL view", "Real browser/native WebGL checks"),
        "AvogadroApp": ("2.0.0", "avogadro.start, avogadro.send, avogadro.capture", "Native companion molecule RPC checks; plugin coverage remains incomplete"),
        "AvogadroLibs": ("2.0.0", "native companion molecule load/export", "Shared Avogadro host; not an independent engine process"),
        "OpenBabel": ("3.1.1", "MOL conversion inside Avogadro", "Companion conversion path only; standalone CLI is not exposed"),
    }
    for entry in catalog["engines"]:
        name = entry["name"]
        source = downloaded.get(name, {})
        supported = [x["operation"] for x in operations if x["engine"] == name]
        runtime = pending_runtime(entry, probes.get(name, {}))
        if name in results and supported:
            evidence = results[name]
            try:
                worker_command(supported[0])
                present = True
            except ValueError:
                present = False
            runtime.update(bundled=present and bool(getattr(sys, "frozen", False)), installed=present, loadable=present, compatible=present, tested=present, integrated=present,
                           status="VERIFIED_OPERATION" if present else "WORKER_UNAVAILABLE", version=evidence["version"],
                           detail="Installed release wheel; reference/smoke checks for listed operations only. It is not built from the downloaded catalog commit.",
                           checked_utc=evidence.get("checked_utc"), evidence_operation=evidence["operation"], resources=evidence.get("resources"))
        if name in existing and _runtime_present(name):
            version, actions, detail = existing[name]
            if version == "rdkit":
                try:
                    version = metadata.version("rdkit")
                except metadata.PackageNotFoundError:
                    version = None
            supported += actions.split(", ")
            avogadro = _avogadro_runtime() if name == "AvogadroApp" else None
            host_tested = bool(avogadro and avogadro["status"] == "RESPONDED")
            bundled = bool(getattr(sys, "frozen", False))
            runtime.update(bundled=bundled, installed=True, loadable=host_tested if avogadro else True,
                           compatible=host_tested if avogadro else True, tested=host_tested if avogadro else False,
                           integrated=True, version=version,
                           status="BUNDLED_CORE" if bundled else "INSTALLED_RUNTIME",
                           detail=detail + ("; bundled in frozen app" if bundled else "; separately installed runtime, not bundled"))
            if avogadro:
                runtime.update(status="RESPONDED" if host_tested else "INSTALLED_NOT_RUNNING", detail=avogadro["scope"], host_status=avogadro)
        rows.append(dict(name=name, tier=entry["tier"], domain=entry["domain"], registered=True,
                         source=dict(downloaded=source.get("status") in {"downloaded", "already_present_verified", "archive_verified"},
                                     repo=entry["source_repo_url"], commit=entry["pinned_commit_sha"], sha256=source.get("sha256"), bytes=source.get("bytes")),
                         runtime=runtime, operations=supported, capabilities=[x for x in operations if x["engine"] == name],
                         scientifically_validated=False, license=dict(reported=entry["license_reported_unverified"], status="NOTICES_PRESERVED; REDISTRIBUTION_REVIEW_REQUIRED"),
                         dependencies=dict(preserved_catalog_boundary=entry["native_host_or_gpu_limit"], included_by_source_archive=False),
                         adapter_boundary=dict(schema="openchem.engine.adapter.v1", engine=name,
                                               interface=entry["interface_class"], python_module=entry.get("python_module"),
                                               executable=entry.get("executable"), runnable_operations=supported,
                                               arbitrary_code_or_shell_allowed=False),
                         scientific_validation="Limited numerical/reference and workflow checks; no general scientific or experimental validation"))
    return dict(schema="openchem.engine.registry.v1", engines=rows,
                counts={key: sum(bool(x["registered"] if key == "registered" else x["source"]["downloaded"] if key == "downloaded" else x["runtime"][key]) for x in rows)
                        for key in ("registered", "downloaded", "installed", "loadable", "compatible", "tested", "integrated")},
                provenance="Catalog commit archives and installed binary releases are separate identities. Evidence timestamps refer to verification, not a continuous running engine.",
                model="No trained production LLM or model weights included")
