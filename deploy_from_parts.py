"""Verify and assemble the static atlas; runs locally or on GitHub Actions."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import zipfile
import sys


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def assemble(root, output):
    manifest = json.loads((root / 'atlas-manifest.json').read_text(encoding='utf-8'))
    expected = manifest['files']
    seen = set()
    # A fresh output prevents stale assets being published after an update.
    output.mkdir(parents=True, exist_ok=False)
    for part in manifest['parts']:
        archive_path = root / part['name']
        if digest(archive_path) != part['sha256']:
            raise ValueError('Archive checksum mismatch: ' + part['name'])
        with zipfile.ZipFile(archive_path) as archive:
            for entry in archive.infolist():
                name = entry.filename
                path = PurePosixPath(name)
                if (entry.is_dir() or path.is_absolute() or '..' in path.parts
                        or '\\' in name or ':' in name or name in seen
                        or name not in expected or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError('Unexpected archive member: ' + name)
                data = archive.read(entry)
                info = expected[name]
                if len(data) != info['bytes'] or hashlib.sha256(data).hexdigest() != info['sha256']:
                    raise ValueError('File checksum mismatch: ' + name)
                target = output.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                seen.add(name)
    if seen != set(expected):
        raise ValueError('Missing files: ' + repr(sorted(set(expected) - seen)))
    if not (output / 'index.html').is_file():
        raise ValueError('Missing root index.html')
    catalog = json.loads((output / 'data/catalog.json').read_text(encoding='utf-8'))
    if len(catalog) != manifest['moduleCount']:
        raise ValueError('Module count mismatch')
    (output / '.nojekyll').touch()
    print(f"Verified {len(seen)} files, {len(catalog)} modules; output: {output}")


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    assemble(root, Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / '_site')
