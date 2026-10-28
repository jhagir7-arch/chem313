"""Split/reassemble a large release without changing its bytes.

Drive connector intake is limited to 100 MiB. Use 90 MiB parts, then verify the
whole SHA-256 after reassembly. This script does not access a network or account.
"""
import argparse
import hashlib
import json
from pathlib import Path

CHUNK = 90 * 1024 * 1024


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def safe_name(name):
    if not isinstance(name, str) or Path(name).name != name or name in {'', '.', '..'}:
        raise ValueError('Manifest contains an unsafe filename')
    return name


def split(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    parts = []
    with source.open('rb') as stream:
        index = 1
        while block := stream.read(CHUNK):
            name = f'{source.name}.part{index:03d}'
            target = destination / name
            with target.open('xb') as output:
                output.write(block)
            parts.append(dict(name=name, bytes=len(block), sha256=hashlib.sha256(block).hexdigest()))
            index += 1
    manifest = dict(schema='openchem.release.parts.v1', filename=source.name,
                    bytes=source.stat().st_size, sha256=digest(source), parts=parts)
    with (destination / f'{source.name}.parts.json').open('x') as output:
        json.dump(manifest, output, indent=2)
        output.write('\n')
    return manifest


def assemble(manifest_path, destination):
    manifest = json.loads(manifest_path.read_text())
    target = destination / safe_name(manifest['filename'])
    # Check every part before creating the output; exclusive creation preserves originals.
    for part in manifest['parts']:
        path = manifest_path.parent / safe_name(part['name'])
        if path.stat().st_size != part['bytes'] or digest(path) != part['sha256']:
            raise ValueError(f'Part failed verification: {path.name}')
    destination.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as output:
        for part in manifest['parts']:
            with (manifest_path.parent / part['name']).open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    output.write(block)
    if target.stat().st_size != manifest['bytes'] or digest(target) != manifest['sha256']:
        raise ValueError('Reassembled file failed verification')
    return dict(status='PASS', filename=target.name, bytes=target.stat().st_size, sha256=manifest['sha256'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['split', 'assemble'])
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    result = split(args.source, args.destination) if args.mode == 'split' else assemble(args.source, args.destination)
    print(json.dumps(result, indent=2))
