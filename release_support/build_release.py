"""Build and verify the installable ZIP. Run with Python 3; no dependencies."""
import hashlib
import json
import re
from pathlib import Path
import zipfile

outputs = Path(__file__).resolve().parent.parent
root = outputs / 'lasgun_comfort'
version = json.loads((root / 'info.json').read_text(encoding='utf-8'))['version']
expected = {
    'lasgun_comfort.mod', 'info.json',
    'scripts/mods/lasgun_comfort/lasgun_comfort.lua',
    'scripts/mods/lasgun_comfort/lasgun_comfort_data.lua',
    'scripts/mods/lasgun_comfort/lasgun_comfort_localization.lua',
}
assert re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?', version), 'Invalid version'
assert not any(p.is_symlink() for p in root.rglob('*')), 'Symlinks cannot ship'
files = {p.relative_to(root).as_posix(): p for p in root.rglob('*') if p.is_file()}
assert set(files) == expected, f'Missing or unexpected release files: {set(files) ^ expected}'
dist = outputs / 'dist'
dist.mkdir(exist_ok=True)
archive = dist / f'lasgun_comfort-{version}.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, source in sorted(files.items()):
        z.write(source, f'lasgun_comfort/{name}')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert set(z.namelist()) == {'lasgun_comfort/' + name for name in expected}
    assert len(z.namelist()) == len(expected)
    for name, source in files.items():
        assert z.read(f'lasgun_comfort/{name}') == source.read_bytes()
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
print(f'Archive verified: {archive.name}; {len(expected)} files; {archive.stat().st_size} bytes')
print(f'SHA-256: {digest}')
