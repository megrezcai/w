"""Package prepared runtime and compiled filters; performs no network operations.
Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
"""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parents[1]
output = root.parent
files = sorted(p for p in root.rglob('*') if p.is_file()
               and '__pycache__' not in p.parts and '.git' not in p.parts
               and p.name != 'SHA256SUMS.txt')
manifest = root/'SHA256SUMS.txt'
manifest.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in files),encoding='utf-8')
files.append(manifest)
archives = []
for name, include_runtime in [('shotcut-surface-text-windows-x64.zip',True),('shotcut-surface-text-sources.zip',False)]:
    destination = output/name
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
            relative = p.relative_to(root)
            if not include_runtime and relative.parts[0]=='runtime': continue
            if not include_runtime and p==manifest:
                source_files=[f for f in files if f!=manifest and f.relative_to(root).parts[0]!='runtime']
                contents=''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.relative_to(root).as_posix()+'\n' for f in source_files)
                z.writestr('shotcut-surface-text/SHA256SUMS.txt',contents)
                continue
            z.write(p,'shotcut-surface-text/'+relative.as_posix())
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None
        assert 'shotcut-surface-text/bin/windows/surfacepin.dll' in z.namelist()
        if include_runtime:
            assert 'shotcut-surface-text/runtime/python.exe' in z.namelist()
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix+'.sha256').write_text(digest+'  '+name+'\n')
    archives.append(dict(file=name,bytes=destination.stat().st_size,sha256=digest))
print(json.dumps(archives,indent=2))
