"""Start the Windows packaged executable and verify bundled assets + API."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    with open(Path(temp)/'process.log','w',encoding='utf-8') as log:
        process=subprocess.Popen([str(root/'dist'/'CaseForge.exe'),'--demo','--no-browser','--port','18765','--data-dir',temp],stdout=log,stderr=log)
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(90):
                try:
                    with opener.open('http://127.0.0.1:18765',timeout=1) as r:html=r.read().decode()
                    break
                except OSError:
                    if process.poll() is not None:raise RuntimeError('Packaged process exited early')
                    time.sleep(.5)
            else:raise RuntimeError('Packaged application did not start')
            token=re.search(r'name="caseforge-token" content="([^"]+)"',html).group(1)
            req=urllib.request.Request('http://127.0.0.1:18765/api/chapters',headers={'X-Caseforge-Token':token})
            with opener.open(req) as r:chapters=json.load(r)
            assert chapters[0]['id']=='rain_manor'
            with opener.open('http://127.0.0.1:18765/app.js') as r:assert b'/api/sessions' in r.read()
            print('Windows executable smoke test passed')
        finally:
            # A PyInstaller one-file exe has a bootloader parent and an app child.
            # Stop the entire test-owned process tree before removing its log/data.
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
