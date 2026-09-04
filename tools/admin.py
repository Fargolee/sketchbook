# -*- coding: utf-8 -*-
"""拾光册 · 藏品管理服务。

    python tools/admin.py          # http://127.0.0.1:4173/admin.html

静态站点照常从仓库根目录提供；管理页通过 /api/pages 读取与写回：
写回时把新画的 PNG 存进 sketchbook/，再把 index.html 里的 PAGES
数组整体重写成提交的清单。只监听 127.0.0.1，别挂到公网。
"""
import base64
import io
import json
import os
import re
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
ART_DIR = "sketchbook"

PAGES_RE = re.compile(r"const PAGES=\[[\s\S]*?\];")
ENTRY_RE = re.compile(
    r"\{file:'(.*?)',\s*title:'(.*?)',\s*place:'(.*?)'(?:,\s*ratio:'(.*?)')?\}")


def unescape(s):
    return s.replace("\\'", "'").replace("\\\\", "\\")


def esc(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def clean_ratio(v):
    try:
        r = float(v)
    except (TypeError, ValueError):
        return None
    return r if 0.2 < r < 5 else None


def read_pages():
    text = INDEX.read_text(encoding="utf-8")
    block = PAGES_RE.search(text)
    if not block:
        raise RuntimeError("index.html 里找不到 PAGES 数组")
    pages = []
    for f, t, p, r in ENTRY_RE.findall(block.group(0)):
        pages.append({
            "file": unescape(f), "title": unescape(t), "place": unescape(p),
            "ratio": clean_ratio(r),
        })
    return pages


def write_pages(pages):
    clean = []
    for p in pages:
        name = os.path.basename(str(p.get("file", "")).strip())
        if not name.endswith(".png"):
            raise ValueError("文件名必须是 .png：%r" % p.get("file"))
        clean.append(
            {
                "file": name,
                "title": str(p.get("title", "")).strip() or name[:-4],
                "place": str(p.get("place", "")).strip(),
                "ratio": clean_ratio(p.get("ratio")),
            }
        )
    if not clean:
        raise ValueError("至少要留一页")
    block = "const PAGES=[\n" + ",\n".join(
        "  {file:'%s', title:'%s', place:'%s'%s}" % (
            p["file"], esc(p["title"]), esc(p["place"]),
            ", ratio:'%.4f'" % p["ratio"] if p["ratio"] else "",
        )
        for p in clean
    ) + "\n];"
    text = INDEX.read_text(encoding="utf-8")
    text, n = PAGES_RE.subn(lambda m: block, text, count=1)
    if n != 1:
        raise RuntimeError("index.html 里找不到 PAGES 数组")
    INDEX.write_text(text, encoding="utf-8")


def save_png(name, b64):
    name = os.path.basename(str(name).strip())
    if not name.endswith(".png"):
        raise ValueError("文件名必须是 .png：%r" % name)
    raw = base64.b64decode(b64)
    try:  # 校验确实是图片；没装 PIL 就放过
        from PIL import Image

        im = Image.open(io.BytesIO(raw))
        im.verify()
    except ImportError:
        pass
    (ROOT / ART_DIR / name).write_bytes(raw)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):  # 本地工具页，禁缓存省得改完看不见
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, body, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/pages":
            try:
                self._json(json.dumps({"pages": read_pages()}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._json(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"), 500)
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/pages":
            self._json(b'{"error":"not found"}', 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            pages = data.get("pages")
            if not isinstance(pages, list):
                raise ValueError("请求里要有 pages 数组")
            for p in pages:
                if p.get("png"):
                    save_png(p.get("file"), p["png"])
            clean = [
                {
                    "file": p.get("file"),
                    "title": p.get("title", ""),
                    "place": p.get("place", ""),
                    "ratio": clean_ratio(p.get("ratio")),
                }
                for p in pages
            ]
            write_pages(clean)
            self._json(json.dumps({"ok": True, "pages": clean}, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._json(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"), 400)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4173
    print("拾光册 · 藏品管理 → http://127.0.0.1:%d/admin.html" % port)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
