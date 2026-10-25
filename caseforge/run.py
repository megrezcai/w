import argparse
import json
from pathlib import Path
import sys
import threading
import webbrowser
from caseforge.server import App, make_server
from caseforge.schema import load

def main():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    install_root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else root
    parser = argparse.ArgumentParser(description='CaseForge: local interrogation and negotiation NPC runtime')
    parser.add_argument('--demo', action='store_true', help='Explicit offline rule demo; not an AI model')
    parser.add_argument('--strict', action='store_true', help='Semantic model + author-written dialogue only')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--model', default='caseforge-npc')
    parser.add_argument('--ollama-url', default='http://127.0.0.1:11434')
    parser.add_argument('--data-dir', type=Path, default=install_root / 'data')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--setup-model', action='store_true')
    parser.add_argument('--base-model', default='qwen3:8b')
    parser.add_argument('--validate', type=Path, help='Validate chapter JSON and exit')
    args = parser.parse_args()
    if args.validate:
        chapter = load(args.validate)
        print('Valid chapter: ' + chapter['id'])
        return 0
    if args.setup_model:
        from setup_model import install
        install(args.base_model, args.model, args.data_dir)
        return 0
    app = App(root, args.data_dir, demo=args.demo, strict=args.strict, model=args.model, base=args.ollama_url)
    server = make_server(app, port=args.port)
    url = f'http://127.0.0.1:{server.server_port}'
    # Local game clients need this per-launch token; it is not a model/API credential.
    print(f'CaseForge: {url}\nBackend: {"RULE DEMO (not AI)" if args.demo else args.model}\nGame API token: {app.token}\nData: {args.data_dir}\nPress Ctrl+C to stop.', flush=True)
    if not args.no_browser:
        threading.Timer(.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
