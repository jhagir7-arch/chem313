"""Check runtime Mach-O architecture, deployment targets and library boundaries."""
import json
import plistlib
from pathlib import Path
import re
import subprocess
import sys

app = Path(sys.argv[1]).resolve()
minimum = plistlib.loads((app/'Contents/Info.plist').read_bytes()).get('LSMinimumSystemVersion', '14.0')
minimum_tuple = tuple((list(map(int, minimum.split('.'))) + [0, 0])[:3])
rows, errors = [], []
for path in sorted(app.rglob('*')):
    if not path.is_file() or path.is_symlink():
        continue
    with path.open('rb') as stream:
        magic = stream.read(4)
    if magic not in {b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'}:
        continue
    architectures = subprocess.check_output(['/usr/bin/lipo', '-archs', str(path)], text=True).strip()
    loads = subprocess.check_output(['/usr/bin/otool', '-L', str(path)], text=True).splitlines()[1:]
    deps = [line.strip().split(' (compatibility')[0] for line in loads]
    bad = [dep for dep in deps if not dep.startswith(('@loader_path/', '@executable_path/', '@rpath/', '/usr/lib/', '/System/Library/'))]
    commands = subprocess.check_output(['/usr/bin/otool', '-l', str(path)], text=True)
    # Only deployment commands, not dylib version fields.
    targets = re.findall(r'cmd LC_BUILD_VERSION[\s\S]*?minos\s+([\d.]+)', commands) + re.findall(r'cmd LC_VERSION_MIN_MACOSX[\s\S]*?version\s+([\d.]+)', commands)
    if 'arm64' not in architectures.split():
        errors.append(f'No arm64 slice: {path.relative_to(app)}')
    if bad:
        errors.append(f'Non-system absolute dependency: {path.relative_to(app)}: {bad}')
    if any(tuple((list(map(int, target.split('.'))) + [0, 0])[:3]) > minimum_tuple for target in targets):
        errors.append(f'Deployment target exceeds declared macOS {minimum}: {path.relative_to(app)}: {targets}')
    rows.append({'path':str(path.relative_to(app)), 'architectures':architectures, 'minimum_os':targets, 'dependencies':deps})
result = {'status':'FAIL' if errors else 'PASS','native_files':len(rows),'errors':errors,'files':rows}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({key:result[key] for key in ('status','native_files','errors')}))
raise SystemExit(bool(errors))
