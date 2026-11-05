import http.server
import socketserver
import os
import webbrowser
import threading

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

class ClimateRequestHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path == "/" or path == "/index.html":
            return os.path.join(BASE_DIR, "site", "index.html")
        elif path.startswith("/data/"):
            return os.path.join(BASE_DIR, "public", path.lstrip("/"))
        return super().translate_path(path)

def open_browser():
    webbrowser.open_new(f"http://localhost:{PORT}")

def start_server():
    os.chdir(BASE_DIR)
    # Ensure port is reusable immediately
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), ClimateRequestHandler) as httpd:
        print(f"============================================================")
        print(f"Afzalpur Taluk Climate Analytics Web App")
        print(f"Running at: http://localhost:{PORT}")
        print(f"Press Ctrl+C to stop.")
        print(f"============================================================")
        threading.Timer(1.0, open_browser).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    start_server()
