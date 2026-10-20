"""Desktop additions to the single RC1 action engine and artifact store."""
from __future__ import annotations

import math
import json
from .engine import Engine
from .approval import request_digest, TTL_SECONDS
from .validation import InputError, PROJECT_RE
from .chemistry import from_smiles, from_molfile, mol_record_info, summary, svg_for
from .conformers import molecule_conformer, relax_geometry, validate_relaxation
from .avogadro_host import AvogadroHost
from .science_jobs import ScienceJobs, validated_params, operation_info, worker_command
from .orca_input import prepare_orca_input
from .orca_runtime import OrcaRuntime


class WorkbenchEngine(Engine):
    _actions = {"molecule.relax_geometry": "project_write", "molecule.generate_conformer": "read_only", "project.save_note": "project_write",
                "orca.prepare_input": "project_write", "orca.run": "project_write", "avogadro.ping": "external_read_only", "avogadro.start": "external_write",
                "avogadro.send": "external_write", "avogadro.capture": "project_write", "science.run": "project_write"}

    def __init__(self, root):
        super().__init__(root)
        self.avogadro = AvogadroHost(self.store.root)
        self.jobs = ScienceJobs(self.store)
        self.orca = OrcaRuntime(self.store)

    def _review_digest(self, action, params, project, effect):
        bound = {**params, 'executable':self.orca.executable_identity()} if action == 'orca.run' else params
        return request_digest(action, bound, project, effect)

    def _validate_desktop(self, action, params, project):
        if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
            raise InputError("Use a project name starting with a letter, with letters, numbers, hyphens or underscores (48 characters maximum)")
        if not isinstance(params, dict):
            raise InputError("Parameters must be an object")
        if action == "molecule.relax_geometry":
            try:
                validate_relaxation(params)
            except ValueError as exc:
                raise InputError(str(exc)) from exc
            return "project_write"
        if action == "science.run":
            validated_params(params)
            worker_command(params["operation"])
            return "project_write"
        if action == "orca.run":
            if set(params) != {"source_artifact"}:
                raise InputError("A saved prepared input artifact is required")
            self.orca._source(project, params["source_artifact"])
            if self.orca.executable is None:
                raise InputError("ORCA is not configured. A licensed macOS ORCA executable is required.")
            return "project_write"
        if action == "orca.prepare_input":
            prepare_orca_input(params)
            return "project_write"
        key = {"molecule.generate_conformer": "smiles", "project.save_note": "text", "avogadro.send": "molfile"}.get(action)
        if key is None:
            if params:
                raise InputError("This Avogadro action takes no parameters")
            return self._actions[action]
        allowed = {key, "seed"} if action == "molecule.generate_conformer" else {key}
        if key not in params or not set(params) <= allowed or not isinstance(params[key], str) or not params[key].strip():
            raise InputError(f"{key} must contain text")
        if action == "molecule.generate_conformer" and "seed" in params:
            seed = params["seed"]
            if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2_147_483_647:
                raise InputError("seed must be an integer from 0 through 2147483647")
        if len(params[key].encode("utf-8")) > (5000 if key == "smiles" else 250_000):
            raise InputError("Input exceeds the supported size")
        if key == "molfile":
            if mol_record_info(params[key])["input_format"] != "MOL_SINGLE_RECORD":
                raise InputError("Avogadro transfer accepts plain MOL only; SDF properties and record framing need a separate metadata-preserving workflow")
            from_molfile(params[key])
        return self._actions[action]

    def preview(self, action, params, project="default"):
        if action not in self._actions:
            return super().preview(action, params, project)
        effect = self._validate_desktop(action, params, project)
        receipt = self._review_digest(action, params, project, effect)
        preview = {"status": "PREVIEW_ONLY", "action": action, "project": project,
                "effect": effect, "request_sha256": receipt,
                "preview_token": self.approvals.preview(receipt) if effect != "read_only" else None,
                "preview_expires_in_seconds": TTL_SECONDS, "requires_explicit_apply": True}
        if action == "orca.run":
            preview["impact"] = "Run this exact saved input locally with ORCA, serially, for up to 300 seconds with a 1 MB output limit. Output and execution report are saved. Normal termination does not establish convergence."
            preview["source_artifact"] = params["source_artifact"]
            preview["executable"] = self.orca.executable_identity()
        if action == "science.run":
            preview["operation"] = operation_info(params["operation"])
            preview["preservation"] = "Exact input request and source text are saved; a numerical report is accepted only after the worker succeeds"
        if action == "orca.prepare_input":
            prepared = prepare_orca_input(params)
            preview["prepared_input"] = prepared["input_text"]
            preview["checks"] = prepared["coordinate_checks"]
            preview["identity_check"] = prepared["identity_check"]
            preview["electron_count"] = prepared["electron_count"]
            preview["settings"] = prepared["settings"]
            preview["warnings"] = prepared["warnings"]
            preview["scope"] = prepared["scope"]
        return preview

    def execute(self, action, params, project="default", approved=False, preview_token=None):
        if action not in self._actions:
            response = super().execute(action, params, project, approved, preview_token)
            if action == "molecule.inspect_smiles":
                mol = from_smiles(params["smiles"])
                response["result"]["svg"] = svg_for(mol)
            return response
        effect = self._validate_desktop(action, params, project)
        if approved is not True:
            raise InputError("Apply requires explicit approved=true")
        if action == "molecule.relax_geometry":
            self.approvals.consume(preview_token, self._review_digest(action, params, project, effect))
            self.store.preflight_event_log(project)
            try:
                result = relax_geometry(params)
            except (ValueError, RuntimeError) as exc:
                raise InputError(str(exc)) from exc
            artifacts = [self.store.put(project, "originals", "sdf", result["initial_sdf"].encode("utf-8")),
                         self.store.put(project, "derived", "sdf", result["sdf"].encode("utf-8"))]
            report = {key: value for key, value in result.items() if key not in {"initial_sdf", "sdf", "svg"}}
            report["geometry_artifacts"] = artifacts.copy()
            artifacts.append(self.store.put(project, "reports", "json", json.dumps(report, indent=2).encode("utf-8")))
            self.store.event(project, action, self._sha(params), artifacts, report)
            return {"status": "EXECUTED", "action": action, "project": project, "result": result, "artifacts": artifacts}
        if action == "orca.run":
            self.approvals.consume(preview_token, self._review_digest(action, params, project, effect))
            job = self.orca.start(project, params["source_artifact"])
            return {"status": "QUEUED", "action": action, "project": project, "job": job, "artifacts": [params["source_artifact"]]}
        if action == "science.run":
            self.approvals.consume(preview_token, self._review_digest(action, params, project, effect))
            job = self.jobs.submit(params, project)
            return {"status": "QUEUED", "action": action, "project": project,
                    "result": {"job_id": job["id"]}, "artifacts": job["artifacts"]}
        if action == "orca.prepare_input":
            self.approvals.consume(preview_token, self._review_digest(action, params, project, effect))
            self.store.preflight_event_log(project)
            result = prepare_orca_input(params)
            artifacts = [
                self.store.put(project, "originals", "sdf", params["geometry_sdf"].encode("utf-8")),
                self.store.put(project, "derived", "inp", result["input_text"].encode("utf-8")),
            ]
            report = {key: value for key, value in result.items() if key != "input_text"}
            artifacts.append(self.store.put(project, "reports", "json", json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")))
            self.store.event(project, action, self._sha(params), artifacts, report)
            return {"status": "EXECUTED", "action": action, "project": project,
                    "result": report, "artifacts": artifacts}
        artifacts = []
        if action == "molecule.generate_conformer":
            mol = from_smiles(params["smiles"])
            if mol.GetNumAtoms() > 100:
                raise InputError("3D generation supports up to 100 heavy atoms in this version")
            try:
                result = molecule_conformer(params)
            except (ValueError, RuntimeError) as exc:
                raise InputError(str(exc)) from exc
            if not math.isfinite(result["energy"]):
                raise InputError("The force field returned a non-finite energy")
            result["scope"] = "One generated force-field conformer, not a global minimum or quantum calculation"
        elif action.startswith("avogadro."):
            self.approvals.consume(preview_token, self._review_digest(action, params, project, effect))
            if action in {"avogadro.ping", "avogadro.start"}:
                result = self.avogadro.status() if action == "avogadro.ping" else self.avogadro.start()
            else:
                self.store.preflight_event_log(project)
                native = self.avogadro.send(params["molfile"]) if action == "avogadro.send" else self.avogadro.capture()
                mol = from_molfile(native)
                result = {"molfile": native, "summary": summary(mol), "host": self.avogadro.status(),
                          "scope": "MOL transfer through Avogadro 2.0.0; advanced plugin and metadata fidelity are not established"}
                if action == "avogadro.send":
                    source = from_molfile(params["molfile"])
                    before, after = summary(source), result["summary"]
                    fields = ["formula", "atom_count", "bond_count", "formal_charge", "isomeric_smiles", "isotope_atoms", "chiral_centers"]
                    checks = {key: before[key] == after[key] for key in fields}
                    checks["atom_map_numbers"] = ([a.GetAtomMapNum() for a in source.GetAtoms()] == [a.GetAtomMapNum() for a in mol.GetAtoms()])
                    coordinates_match = source.GetNumAtoms() == mol.GetNumAtoms() and source.GetNumConformers() == mol.GetNumConformers()
                    if coordinates_match and source.GetNumConformers():
                        delta = abs(source.GetConformer().GetPositions() - mol.GetConformer().GetPositions())
                        coordinates_match = bool((delta <= .0002).all())
                    checks["coordinates_within_0_0002_angstrom"] = coordinates_match
                    result["field_checks"] = checks
                    result["fidelity_status"] = "CHECKED_FIELDS_MATCH" if all(checks.values()) else "DIFFERENCE_DETECTED"
                    artifacts.append(self.store.put(project, "originals", "mol", params["molfile"].encode("utf-8")))
                artifacts.append(self.store.put(project, "derived" if action == "avogadro.send" else "originals", "mol", native.encode("utf-8")))
                report = json.dumps({k: v for k, v in result.items() if k != "molfile"}, ensure_ascii=False, indent=2).encode("utf-8")
                artifacts.append(self.store.put(project, "reports", "json", report))
                self.store.event(project, action, self._sha(params), artifacts, result)
        else:
            self.approvals.consume(preview_token, self._review_digest(action, params, project, effect))
            self.store.preflight_event_log(project)
            artifacts = [self.store.put(project, "originals", "txt", params["text"].encode("utf-8"))]
            result = {"text": params["text"], "characters": len(params["text"])}
            self.store.event(project, action, self._sha(params), artifacts, result)
        return {"status": "EXECUTED", "action": action, "project": project,
                "result": result, "artifacts": artifacts}
