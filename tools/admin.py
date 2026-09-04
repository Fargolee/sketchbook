# -*- coding: utf-8 -*-
"""拾光册 · 藏品管理服务。

    python tools/admin.py                       # 仅本机访问（默认，最安全）
    python tools/admin.py --open                # 启动后自动打开浏览器
    python tools/admin.py --lan                 # 局域网内可访问（手机/其他电脑）
    python tools/admin.py --lan --password 口令  # 固定口令
    python tools/admin.py 5000                  # 换端口

口令验证永远开启：--password 指定固定口令；不给就自动生成一个，存到
根目录 .adminpass（已 gitignore，不会发布），之后每次启动沿用。
管理页 /admin.html 与读写接口 /api/pages 都要验这个口令。
--lan 只建议在可信的家里 Wi-Fi 用，公网暴露请配合 Tailscale 这类私有隧道。
"""
import base64
import io
import json
import os
import re
import secrets
import socket
import string
import sys
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
ART_DIR = "sketchbook"

PASSWORD = None  # 由命令行 --password 注入

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
            if self.headers.get("X-Admin-Token") != PASSWORD:
                self._json('{"error":"管理口令不对"}'.encode("utf-8"), 401)
                return
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
        if PASSWORD and self.headers.get("X-Admin-Token") != PASSWORD:
            self._json('{"error":"管理口令不对"}'.encode("utf-8"), 401)
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


class Server(HTTPServer):
    # Windows 的 SO_REUSEADDR 允许同一端口被绑两次，双开还不报错；
    # 关掉它，端口被占时才会走下面的友好提示。
    allow_reuse_address = (os.name != "nt")


if __name__ == "__main__":
    args = sys.argv[1:]
    host = "127.0.0.1"
    if "--lan" in args:
        args.remove("--lan")
        host = "0.0.0.0"
    password = None
    pass_source = ""
    if "--password" in args:
        i = args.index("--password")
        password = args[i + 1]
        del args[i:i + 2]
        pass_source = "命令行 --password"
    if not password:  # 没给固定口令：沿用 .adminpass，或生成一个存进去
        pf = ROOT / ".adminpass"
        if pf.exists():
            password = pf.read_text(encoding="utf-8").strip()
            pass_source = "沿用 .adminpass 里保存的"
        else:
            alphabet = string.ascii_lowercase + string.digits
            password = "".join(secrets.choice(alphabet) for _ in range(8))
            pf.write_text(password, encoding="utf-8")
            pass_source = "自动生成，已保存到 .adminpass"
    open_page = "--open" in args
    if open_page:
        args.remove("--open")
    port = int(args[0]) if args else 4173
    PASSWORD = password
    if open_page:
        open_after_start = threading.Timer(
            0.8, webbrowser.open, args=("http://127.0.0.1:%d/" % port,))
        open_after_start.daemon = True
        open_after_start.start()

    print("拾光册 · 藏品管理 → http://127.0.0.1:%d/admin.html" % port)
    print("管理口令：%s（%s）——管理页首次进入时输入一次" % (password, pass_source))
    if host == "0.0.0.0":
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
            s.close()
        except Exception:
            lan_ip = "<本机局域网IP>"
        hint = " → http://%s:%d/admin.html（局域网）" % (lan_ip, port)
        print("局域网访问%s" % hint)
        print("首次运行 Windows 可能弹防火墙询问，勾选允许；或以管理员执行：")
        print('  netsh advfirewall firewall add rule name="sketchbook-admin" dir=in action=allow protocol=TCP localport=%d' % port)
        if password:
            print("已启用口令：写入接口需要 X-Admin-Token 与之一致")
        else:
            print("注意：未设口令，局域网内任何人都能改动册子；建议加 --password")
    try:
        Server((host, port), Handler).serve_forever()
    except OSError:
        print("端口 %d 被占用：服务可能已经在运行；要换端口可执行 python tools/admin.py 5000" % port)
    except KeyboardInterrupt:
        print("已停止")
