"""Build a Python-free Windows distribution. Run on Windows, or use repository CI."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parent

def main():
    if sys.platform!='win32':
        raise SystemExit('Build this Windows executable on Windows; use the GitHub Actions workflow.')
    subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--name','CaseForge',
                    '--add-data',f'caseforge/web{os.pathsep}caseforge/web',
                    '--add-data',f'chapters{os.pathsep}chapters','run.py'],cwd=ROOT,check=True)
    folder=ROOT/'dist'/'CaseForge'
    if folder.exists():shutil.rmtree(folder)
    folder.mkdir()
    shutil.copy2(ROOT/'dist'/'CaseForge.exe',folder/'CaseForge.exe')
    for name in ['START.cmd','SETUP-MODEL.cmd','DEMO.cmd','README.md','LICENSE','Modelfile']:
        shutil.copy2(ROOT/name,folder/name)
    for name in ['chapters','docs','integrations']:
        shutil.copytree(ROOT/name,folder/name)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.exists():
        shutil.copy2(python_license, folder/'docs'/'Python-LICENSE.txt')
    from importlib.metadata import distribution
    builder = distribution('pyinstaller')
    for entry in builder.files or []:
        if str(entry).endswith('/COPYING.txt'):
            shutil.copy2(builder.locate_file(entry), folder/'docs'/'PyInstaller-COPYING.txt')
            break
    archive=ROOT/'dist'/'CaseForge-Windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in sorted(folder.rglob('*')):
            if file.is_file():z.write(file,Path('CaseForge')/file.relative_to(folder))
    print(archive)

if __name__=='__main__':main()
