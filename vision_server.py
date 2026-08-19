from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from vision_core import ROOT, VisionWorker


class Handler(SimpleHTTPRequestHandler):
    worker: VisionWorker = None
    static_root: Path = ROOT

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.static_root), **kwargs)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            body = json.dumps(self.worker.get_state(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/screenshot.jpg":
            body = self.worker.get_jpeg()
            if body is None:
                self.send_error(503, "no screenshot yet")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/":
            self.path = "/live.html"
        return super().do_GET()

    def log_message(self, fmt, *args):
        # keep console readable; API polling is intentionally quiet
        if "/api/state" not in (args[0] if args else ""):
            super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser(description="牌桌军师 Android 实时视觉桥接服务")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--capture-mode", choices=("auto", "adb", "window"), default=None)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    cfg_path = ROOT / args.config
    worker = VisionWorker(cfg_path, {"capture_mode": args.capture_mode})
    worker.start()
    Handler.worker = worker
    Handler.static_root = ROOT

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"牌桌军师实时助手: {url}")
    print("支持 Android ADB 与 iPhone AirPlay 投屏窗口；首次使用请先标定并学习模板。")
    if not args.no_browser:
        opener = threading.Timer(0.8, lambda: webbrowser.open(url))
        opener.daemon = True
        opener.start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        worker.stop()
        httpd.server_close()


if __name__ == "__main__":
    main()
