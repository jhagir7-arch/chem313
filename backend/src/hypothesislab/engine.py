"""Actions return machine-verifiable outputs, never guessed tool successes."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from .chemistry import from_smiles, from_molfile, mol_record_info, summary, svg_for, fidelity
from .store import Store
from .validation import validate, InputError
from .avogadro import ping
from .measurements import fit_csv, validate_csv_structure
from .approval import ApprovalLedger, action_v2_digest, request_digest, TTL_SECONDS

class Engine:
    def __init__(self, root: str | Path):
        self.store = Store(root)
        self.approvals = ApprovalLedger(self.store.root)

    def preview(self, action: str, params: dict[str, Any], project: str = "default") -> dict:
        effect = validate(action, params, project)
        # Reject malformed source before issuing an approval that can never apply.
        # This does not normalize or store source bytes.
        if action == "measurement.fit_csv":
            validate_csv_structure(params["csv"], params["x_column"], params["y_column"])
        elif action == "molecule.import_molfile":
            # The core importer preserves one MOL plus optional SDF properties,
            # but refuses SDF record framing pending a dedicated importer.
            if "$$$$" in params["molfile"]:
                raise InputError("SDF record delimiters require a dedicated validated SDF importer; no partial import")
            mol_record_info(params["molfile"])
            from_molfile(params["molfile"])
        elif action == "molecule.fidelity_audit":
            mol_record_info(params["molfile"])
        receipt = request_digest(action, params, project, effect)
        token = self.approvals.preview(receipt) if effect != "read_only" else None
        return {
            "status": "PREVIEW_ONLY", "action":action, "project":project,
            "effect": effect, "input_sha256": self._sha(params),
            "request_sha256": receipt, "action_v2_sha256": action_v2_digest(action, params, project), "preview_token": token,
            "preview_expires_in_seconds": TTL_SECONDS if token else None,
            "requires_explicit_apply": True,
            "supported": True,
            "warning": "No chemistry, host command or project artifact was produced; an approval record was stored",
        }

    @staticmethod
    def _sha(params: dict) -> str:
        return sha256(json.dumps(params, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode()).hexdigest()

    @staticmethod
    def request_sha(action: str, params: dict[str, Any], project: str = "default") -> str:
        return action_v2_digest(action, params, project)

    def execute(self, action: str, params: dict[str, Any], project: str = "default", approved: bool = False, preview_token: str | None = None) -> dict:
        effect = validate(action, params, project)
        if approved is not True:
            raise InputError("Apply requires explicit approved=true")
        if effect != "read_only":
            self.approvals.consume(preview_token, request_digest(action, params, project, effect))
        if effect == "project_write":
            self.store.preflight_event_log(project)
        artifacts = []
        if action == "molecule.inspect_smiles":
            mol = from_smiles(params["smiles"])
            report = summary(mol)
            # Read-only computation, no side effects or audit event
            return {"status":"EXECUTED", "action":action, "project":project, "result": report, "artifacts": []}
        elif action == "molecule.fidelity_audit":
            result = fidelity(params["molfile"])
            # Derived full MOL is not persisted by fidelity audit; summarize and withhold bulk payload
            result = {k:v for k,v in result.items() if k != "normalized_molfile"}
            return {"status":"EXECUTED", "action":action, "project":project, "result":result, "artifacts":[]}
        elif action == "molecule.import_molfile":
            molfile = params["molfile"]
            if "$$$$" in molfile:
                raise InputError("SDF record delimiters require a dedicated validated SDF importer; no partial import")
            test = fidelity(molfile)
            mol = from_molfile(molfile)
            artifacts.append(self.store.put(project, "originals", "mol", molfile.encode("utf-8")))
            artifacts.append(self.store.put(project, "derived", "mol", test["normalized_molfile"].encode("utf-8")))
            artifacts.append(self.store.put(project, "derived", "svg", svg_for(mol).encode("utf-8")))
            result = {"summary":summary(mol), "fidelity":{k:v for k,v in test.items() if k not in ("normalized_molfile", "summary")}}
            report_blob = json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2).encode()
            artifacts.append(self.store.put(project, "reports", "json", report_blob))
            event = self.store.event(project, action, self._sha(params), artifacts, result)
            status = "EXECUTED_WITH_COMPATIBILITY_WARNINGS" if result["fidelity"]["warnings"] else "EXECUTED"
            return {"status":status, "action":action, "project":project, "result":result, "artifacts":artifacts, "event_utc":event["timestamp_utc"]}
        elif action == "measurement.fit_csv":
            result, svg = fit_csv(**params)
            artifacts.append(self.store.put(project, "originals", "csv", params["csv"].encode("utf-8")))
            artifacts.append(self.store.put(project, "derived", "svg", svg))
            artifacts.append(self.store.put(project, "reports", "json", json.dumps(result, sort_keys=True, indent=2).encode("utf-8")))
            event = self.store.event(project, action, self._sha(params), artifacts, result)
            return {"status":"EXECUTED", "action":action, "project":project, "result":result, "artifacts":artifacts, "event_utc":event["timestamp_utc"]}
        elif action == "avogadro.ping":
            # Presence check is read-only; native host/plugin fidelity is not implied.
            return {"status":"EXECUTED", "action":action, "project":project, "result":ping(), "artifacts": []}
        raise InputError("Unimplemented action")
