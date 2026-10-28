"""Preserve notices and distribution identities from the current environment."""
from importlib.metadata import distributions
import hashlib
import json
from pathlib import Path
import sys

target = Path(sys.argv[1])
target.mkdir(parents=True, exist_ok=True)
rows = []
for dist in sorted(distributions(), key=lambda x: x.metadata.get("Name", "").lower()):
    name = dist.metadata.get("Name", "unknown")
    folder = target / name
    notices = []
    for file in dist.files or []:
        if not any(part.lower().startswith(("license", "copying", "notice", "copyright")) for part in file.parts):
            continue
        path = Path(dist.locate_file(file))
        if not path.is_file() or path.stat().st_size > 2000000:
            continue
        raw = path.read_bytes()
        # Flatten directory traversal segments from dist-info/RECORD paths.
        destination = folder.joinpath(*[x for x in file.parts if x not in {"..", ".", "/"}])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        notices.append(dict(path=str(destination.relative_to(target)), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)))
    rows.append(dict(name=name, version=dist.version, license=dist.metadata.get("License-Expression") or dist.metadata.get("License"),
                     project_urls=dist.metadata.get_all("Project-URL"), notices=notices,
                     runtime_source="Installed distribution; not asserted equivalent to source-vault commit",
                     redistribution_review="REQUIRED"))
(target / "DISTRIBUTIONS.json").write_text(json.dumps(rows, indent=2))
print(f"Preserved notices/metadata for {len(rows)} installed distributions")
