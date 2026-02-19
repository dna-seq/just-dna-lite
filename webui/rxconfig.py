import reflex as rx
import os
import socket


def _find_free_port(start: int = 8000, end: int = 9000) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    return start


backend_port = int(os.getenv("BACKEND_PORT", "0")) or _find_free_port(8000)
api_url = os.getenv("API_URL", f"http://localhost:{backend_port}")

# Persist so state.py's backend_api_url computed var reads the correct port
os.environ["API_URL"] = api_url

config = rx.Config(
    app_name="webui",
    backend_port=backend_port,
    api_url=api_url,
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    # Fomantic UI styling
    stylesheets=[
        "https://cdn.jsdelivr.net/npm/fomantic-ui@2.9.4/dist/semantic.min.css",
    ],
    # jQuery and Fomantic UI JS for interactive components
    head_components=[
        rx.script(src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"),
        rx.script(src="https://cdn.jsdelivr.net/npm/fomantic-ui@2.9.4/dist/semantic.min.js"),
    ],
    # Tailwind is disabled
    tailwind=None,
)
