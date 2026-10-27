"""Локальный просмотр dist/ с адресами без .html (как на nginx). python -I serve.py [порт]"""
import http.server, os, sys

DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=DIST, **k)

    def send_head(self):
        path = self.translate_path(self.path)
        if not os.path.exists(path) and os.path.exists(path + ".html"):
            self.path = self.path.split("?")[0] + ".html"
        elif os.path.isdir(path) and os.path.exists(path.rstrip("/\\") + ".html") and not self.path.endswith("/"):
            self.path = self.path.split("?")[0] + ".html"
        elif not os.path.exists(path):
            self.send_response(404)
            body = open(os.path.join(DIST, "404.html"), "rb").read()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            from io import BytesIO
            return BytesIO(body)
        return super().send_head()

    def log_message(self, *a):
        pass


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8059
print(f"http://localhost:{port}")
http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
