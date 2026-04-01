"""Simple static frontend server for the dashboard."""

from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
from pathlib import Path

PORT = 3000
WEB_ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    """Serve files from frontend directory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)


if __name__ == "__main__":
    with TCPServer(("", PORT), Handler) as httpd:
        print(f"Frontend dashboard available at http://localhost:{PORT}")
        httpd.serve_forever()
