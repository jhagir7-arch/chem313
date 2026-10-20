"""Local desktop service: one action engine, same-origin UI, immutable files."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
from datetime import datetime, timezone


def platform_data_dir(*, environ=None, system=None, home=None) -> Path:
    """Return the per-user data directory without assuming macOS paths."""
    environ = os.environ if environ is None else environ
    system = sys.platform if system is None else system
    home_path = Path.home() if home is None else Path(home)
    if system.startswith("win"):
        local = environ.get("LOCALAPPDATA")
        return Path(local) / "OpenChem" if local else home_path / "AppData" / "Local" / "OpenChem"
    if system.startswith("linux"):
        xdg = environ.get("XDG_DATA_HOME")
        return Path(xdg) / "OpenChem" if xdg else home_path / ".local" / "share" / "OpenChem"
    return home_path / "Library" / "Application Support" / "OpenChem"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data")
    parser.add_argument("--ui")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)
    if args.data:
        os.environ["HYPOTHESISLAB_DATA"] = args.data
    else:
        os.environ.setdefault("HYPOTHESISLAB_DATA", str(platform_data_dir()))
    os.environ.setdefault("MPLCONFIGDIR", str(Path(os.environ["HYPOTHESISLAB_DATA"])/".matplotlib"))

    from . import api, __version__
    from .workbench import WorkbenchEngine
    from .validation import InputError, PROJECT_RE
    from fastapi import Request, HTTPException, Security
    from fastapi.responses import Response, FileResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn

    api.engine = WorkbenchEngine(api.ROOT)
    app = api.app
    from .science_api import register
    register(app, api)
    from .calculation_api import register as register_calculations
    register_calculations(app, api)
    from .study_api import register as register_studies
    register_studies(app, api)
    from .qchem_api import register as register_qchem
    register_qchem(app, api)
    from .assistant import Assistant
    from .orca_runtime import executable_status

    @app.get("/api/workbench")
    def workbench(request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        from rdkit import rdBase
        import scipy
        projects = []
        for p in sorted(api.ROOT.iterdir()):
            if not p.is_symlink() and p.is_dir() and PROJECT_RE.fullmatch(p.name):
                projects.append(p.name)
        return {"name": "OpenChem", "version": __version__, "projects": projects,
                "data_directory": str(api.ROOT), "engines": {"rdkit": rdBase.rdkitVersion,
                "scipy": scipy.__version__, "ketcher": "3.18.0"},
                "avogadro": api.engine.avogadro.status(), "orca_engine": executable_status(api.engine.orca.executable, discover=False),
                "llm": Assistant(api.ROOT).status(), "native_plugins": "Only molecule load/export verified"}

    @app.get("/api/engines/check")
    def check_engines(request: Request, token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        from rdkit import Chem, rdBase
        from scipy.stats import linregress
        import scipy
        checks = []
        for name, version, probe in [
            ("RDKit", rdBase.rdkitVersion, lambda: Chem.MolToSmiles(Chem.MolFromSmiles("CCO")) == "CCO"),
            ("SciPy", scipy.__version__, lambda: abs(linregress([0, 1, 2], [1, 3, 5]).slope - 2) < 1e-12),
        ]:
            try:
                ok = bool(probe())
                checks.append({"name": name, "version": version, "status": "PASS" if ok else "FAIL"})
            except Exception as exc:
                checks.append({"name": name, "version": version, "status": "FAIL", "detail": type(exc).__name__})
        return {"checked_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
                "avogadro": api.engine.avogadro.status(), "orca_engine": executable_status(api.engine.orca.executable, discover=False),
                "llm": Assistant(api.ROOT).status()}

    @app.get("/api/projects/{project}/artifact/{group}/{filename}")
    def artifact(project: str, group: str, filename: str, request: Request,
                 token: str | None = Security(api.SESSION_HEADER)):
        api.require_session(request, token)
        if not PROJECT_RE.fullmatch(project) or group not in {"originals", "derived", "reports"} or not re.fullmatch(r"[0-9a-f]{64}\.(mol|sdf|inp|svg|json|csv|txt)", filename):
            raise HTTPException(404)
        relative = f"{project}/{group}/{filename}"
        try:
            events = api.engine.store.events(project, 100)
            expected = next((a for e in events for a in e.get("artifacts", []) if a.get("relative_path") == relative), None)
            if expected is None:
                raise HTTPException(404)
            p = api.ROOT / project / group / filename
            if any(q.is_symlink() for q in (api.ROOT/project, p.parent, p)):
                raise HTTPException(404)
            with p.open("rb") as stream:
                content = stream.read(1_000_001)
            if len(content) != expected["bytes"] or hashlib.sha256(content).hexdigest() != expected["sha256"]:
                raise HTTPException(409, "Saved file failed its integrity check")
        except (OSError, InputError) as exc:
            raise HTTPException(422, str(exc)) from exc
        mime = {"svg": "image/svg+xml", "json": "application/json"}.get(p.suffix[1:], "text/plain; charset=utf-8")
        return Response(content, media_type=mime, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    ui = Path(args.ui) if args.ui else Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[4])) / "ui"
    if not ui.is_dir():
        raise SystemExit("Built interface missing; use --ui frontend/dist for development")
    app.mount("/", StaticFiles(directory=ui, html=True), name="interface")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", args.port))
    listener.listen(128)
    print(json.dumps({"url": f"http://127.0.0.1:{listener.getsockname()[1]}", "pid": os.getpid()}), flush=True)
    uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False)).run(sockets=[listener])


if __name__ == "__main__":
    main()
