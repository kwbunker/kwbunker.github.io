#!/usr/bin/env python3
"""
Simple static site generator using Jinja2 and Markdown.

Usage:
    uv run python build.py          # Build the site
    uv run python build.py serve    # Build and serve locally
    uv run python build.py watch    # Build, serve, and watch for changes
"""

import http.server
import shutil
import socketserver
import sys
import re
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader

# Paths
ROOT = Path(__file__).parent
TEMPLATES_DIR = ROOT / "templates"
CONTENT_DIR = ROOT / "content"
OUTPUT_DIR = ROOT / "docs"
STATIC_DIR = ROOT / "static"

# Site configuration
SITE = {
    "title": "Kristopher Bunker",
    "url": "https://www.kristopherbunker.com",
    "social": {
        "github": "https://github.com/kwbunker",
        "linkedin": "https://linkedin.com/in/kwbunker",
    },
}


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML-like frontmatter from markdown content."""
    frontmatter = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip().strip('"')
            body = parts[2].strip()

    return frontmatter, body


def load_content(content_file: Path) -> dict:
    """Load a markdown content file and return parsed data."""
    text = content_file.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)

    md = markdown.Markdown(extensions=["meta", "fenced_code", "tables"])
    html = md.convert(body)

    return {
        "slug": content_file.stem,
        "html": html,
        "body": body,
        **frontmatter,
    }


def build():
    """Build the static site."""
    print("Building site...")

    # Clean and create output directory
    cname_content = None
    if OUTPUT_DIR.exists():
        # Preserve CNAME file if it exists
        cname_file = OUTPUT_DIR / "CNAME"
        if cname_file.exists():
            cname_content = cname_file.read_text()

        shutil.rmtree(OUTPUT_DIR)

    OUTPUT_DIR.mkdir(parents=True)

    # Restore CNAME
    if cname_content:
        (OUTPUT_DIR / "CNAME").write_text(cname_content)
    else:
        # Create default CNAME
        (OUTPUT_DIR / "CNAME").write_text("www.kristopherbunker.com")

    # Copy static files
    if STATIC_DIR.exists():
        for item in STATIC_DIR.iterdir():
            dest = OUTPUT_DIR / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        print(f"  Copied static files")

    # Set up Jinja2
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

    # Load all content
    pages = {}
    if CONTENT_DIR.exists():
        for content_file in CONTENT_DIR.glob("*.md"):
            page = load_content(content_file)
            pages[page["slug"]] = page
            print(f"  Loaded content: {content_file.name}")

    # Render index page
    template = env.get_template("index.html")
    html = template.render(site=SITE, pages=pages)
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"  Rendered: index.html")

    print(f"Build complete! Output in: {OUTPUT_DIR}")


def serve(port: int = 8000):
    """Serve the built site locally."""
    import os
    os.chdir(OUTPUT_DIR)

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving at http://localhost:{port}")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def watch(port: int = 8000):
    """Watch for changes and rebuild automatically."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("watchdog not installed. Run: uv sync")
        sys.exit(1)

    import threading
    import time

    class RebuildHandler(FileSystemEventHandler):
        def __init__(self):
            self.last_build = 0

        def on_any_event(self, event):
            # Debounce rebuilds
            if time.time() - self.last_build < 1:
                return
            if event.src_path and not any(x in event.src_path for x in ["docs", ".git", "__pycache__"]):
                print(f"\nChange detected: {event.src_path}")
                build()
                self.last_build = time.time()

    # Initial build
    build()

    # Start file watcher
    observer = Observer()
    observer.schedule(RebuildHandler(), str(ROOT), recursive=True)
    observer.start()

    # Start server in background
    server_thread = threading.Thread(target=serve, args=(port,), daemon=True)
    server_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        if command == "serve":
            build()
            serve(port)
        elif command == "watch":
            watch(port)
        else:
            print(f"Unknown command: {command}")
            print("Usage: build.py [serve|watch] [port]")
    else:
        build()
