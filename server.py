# -*- coding: utf-8 -*-
"""
代码转换器 · 本地服务
仅监听 127.0.0.1，供本机浏览器访问。
功能：
  GET  /                   静态界面
  GET  /api/env            运行环境检测
  GET  /api/langs          语言元数据
  POST /api/run            编译/运行指定语言的代码
  POST /api/convert        规则引擎转换
  POST /api/convert_ai     接入 OpenAI 兼容接口的 AI 转换
双击「启动代码转换器.bat」即可运行本服务。
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
DEFAULT_PORT = 8765
RUN_TIMEOUT = 15        # 秒
AI_TIMEOUT = 120        # 秒
MAX_OUTPUT = 200_000    # 字节
MAX_CODE = 200_000      # 字节

LANG_EXT = {"c": "c", "cpp": "cpp", "python": "py", "javascript": "js"}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def run_process(args, stdin_data="", timeout=RUN_TIMEOUT, cwd=None):
    """运行子进程，捕获输出，超时强杀"""
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    start = time.time()
    try:
        p = subprocess.run(
            args,
            input=stdin_data.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            creationflags=flags,
        )
        out = (p.stdout + b"\n" + p.stderr).decode("utf-8", "replace").strip("\n")
        return p.returncode, out, int((time.time() - start) * 1000)
    except subprocess.TimeoutExpired as e:
        # 超时：尝试强杀进程树
        if e.pid and os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(e.pid), "/T", "/F"],
                    capture_output=True, timeout=5,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass
        return -9, f"运行超时（超过 {timeout} 秒），已强制终止。\n请检查代码是否有死循环。", int((time.time() - start) * 1000)
    except FileNotFoundError as e:
        return -2, f"找不到可执行文件：{e.filename}", 0


def detect_env():
    env = {}

    def ver(cmd):
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=10,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return p.stdout.decode("utf-8", "replace").strip().splitlines()
        except Exception:
            return []

    gcc = shutil.which("gcc")
    gpp = shutil.which("g++")
    node = shutil.which("node")
    env["c"] = {"available": bool(gcc), "cmd": gcc, "version": (ver([gcc, "--version"]) or [""])[0] if gcc else ""}
    env["cpp"] = {"available": bool(gpp), "cmd": gpp, "version": (ver([gpp, "--version"]) or [""])[0] if gpp else ""}
    env["python"] = {"available": True, "cmd": sys.executable, "version": (ver([sys.executable, "--version"]) or [""])[0]}
    env["javascript"] = {"available": bool(node), "cmd": node, "version": (ver([node, "--version"]) or [""])[0] if node else ""}
    return env


LANGS = [
    {"id": "c", "name": "C", "ext": "c"},
    {"id": "cpp", "name": "C++", "ext": "cpp"},
    {"id": "python", "name": "Python", "ext": "py"},
    {"id": "javascript", "name": "JavaScript", "ext": "js"},
]


def run_code(lang, code, stdin_data=""):
    """编译并运行代码，返回 dict"""
    if lang not in LANG_EXT:
        return {"ok": False, "error": f"不支持的语言: {lang}"}
    if len(code.encode("utf-8")) > MAX_CODE:
        return {"ok": False, "error": "代码过长"}
    env = detect_env()
    if not env[lang]["available"]:
        return {"ok": False, "error": f"本机未检测到 {lang} 的运行环境（{env[lang]['cmd'] or '未安装'}），无法运行。请安装后重启本软件。"}

    tmp = tempfile.mkdtemp(prefix="ccode_")
    src = os.path.join(tmp, f"main.{LANG_EXT[lang]}")
    with open(src, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)

    if lang in ("c", "cpp"):
        exe = os.path.join(tmp, "main.exe")
        cc = env[lang]["cmd"]
        rc, out, ms = run_process([cc, src, "-o", exe, "-O2", "-Wall", "-lm"], cwd=tmp, timeout=30)
        if rc != 0:
            return {"ok": False, "stage": "compile", "output": out or "编译失败", "elapsed_ms": ms}
        rc, out, ms = run_process([exe], stdin_data, cwd=tmp)
    elif lang == "python":
        rc, out, ms = run_process([env["python"]["cmd"], src], stdin_data, cwd=tmp)
    elif lang == "javascript":
        rc, out, ms = run_process([env["javascript"]["cmd"], src], stdin_data, cwd=tmp)
    else:
        return {"ok": False, "error": "不支持的语言"}

    if len(out) > MAX_OUTPUT:
        out = out[:MAX_OUTPUT] + "\n…（输出过长已截断）"
    return {"ok": rc == 0, "exit_code": rc, "output": out, "elapsed_ms": ms}


def strip_code_fence(text):
    """去掉 AI 输出里可能带的 ``` 围栏"""
    t = text.strip()
    lines = t.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip("\n")


def convert_with_ai(source, src_lang, dst_lang, base_url, api_key, model):
    """调用 OpenAI 兼容接口做代码转换"""
    if not source.strip():
        return False, "源代码为空"
    base_url = base_url.rstrip("/")
    url = base_url + "/chat/completions"
    system = (
        "你是一位资深的程序语言转换专家，擅长把一段代码从一种语言准确、完整地转换为另一种语言。"
        "转换要求：\n"
        "1) 只输出目标语言的代码本身，不要输出任何解释、说明或 markdown 代码块围栏；\n"
        "2) 保持原代码的功能、算法和逻辑完全一致；\n"
        "3) 注意处理两种语言的输入输出差异（如 printf/scanf 与 print/input、cin/cout 与 console.log 等），"
        "保证转换后的代码可直接编译/运行；\n"
        "4) 若某些写法在目标语言中没有直接对应，给出等价的实现并保持可运行。"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"请把下面的 {src_lang} 代码转换为 {dst_lang} 代码：\n```\n{source}\n```"},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=AI_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return True, strip_code_fence(content)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            detail = ""
        return False, f"AI 接口返回错误（HTTP {e.code}）：{detail}"
    except urllib.error.URLError as e:
        return False, f"无法连接 AI 接口：{e.reason}"
    except Exception as e:
        return False, f"AI 转换失败：{e}"


class Handler(BaseHTTPRequestHandler):
    server_version = "CodeConverter/1.0"

    def log_message(self, fmt, *args):
        pass  # 安静运行

    # ---- 工具 ----
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > 2_000_000:
                return None
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    # ---- 路由 ----
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/api/env", "/api/env/"):
            return self.send_json(detect_env())
        if path in ("/api/langs", "/api/langs/"):
            return self.send_json(LANGS)
        return self.serve_static(path)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        data = self.read_json()
        if data is None:
            return self.send_json({"ok": False, "error": "请求格式错误"}, 400)

        if path in ("/api/run", "/api/run/"):
            lang = data.get("lang", "")
            code = data.get("code", "")
            stdin_data = data.get("stdin", "") or ""
            if not code.strip():
                return self.send_json({"ok": False, "error": "代码为空"})
            result = run_code(lang, code, stdin_data)
            return self.send_json(result)

        if path in ("/api/convert", "/api/convert/"):
            from converter import rule_engine
            source = data.get("source", "")
            src = data.get("from", "")
            dst = data.get("to", "")
            ok, result = rule_engine.convert(source, src, dst)
            if ok:
                return self.send_json({"ok": True, "engine": "rule", "code": result,
                                       "note": "规则引擎输出，请人工核对后再使用"})
            return self.send_json({"ok": False, "engine": "rule", "error": result})

        if path in ("/api/convert_ai", "/api/convert_ai/"):
            source = data.get("source", "")
            src = data.get("from", "")
            dst = data.get("to", "")
            base_url = (data.get("base_url") or "").strip()
            api_key = (data.get("api_key") or "").strip()
            model = (data.get("model") or "").strip() or "deepseek-chat"
            if not base_url or not api_key:
                return self.send_json({"ok": False, "error": "请先在「AI 设置」中配置接口地址与 API Key"})
            ok, result = convert_with_ai(source, src, dst, base_url, api_key, model)
            if ok:
                return self.send_json({"ok": True, "engine": "ai", "code": result})
            return self.send_json({"ok": False, "engine": "ai", "error": result})

        return self.send_json({"ok": False, "error": "未知接口"}, 404)

    # ---- 静态文件 ----
    def serve_static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        rel = path.lstrip("/")
        target = (WEB / rel).resolve()
        # 防目录穿越
        if not str(target).startswith(str(WEB.resolve())) or not target.is_file():
            self.send_error(404, "Not Found")
            return
        ext = target.suffix.lower()
        ctype = MIME.get(ext, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


def find_free_port(start):
    for port in range(start, start + 50):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            return port, srv
        except OSError:
            continue
    return None, None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="代码转换器 本地服务")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="起始端口")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()

    port, srv = find_free_port(args.port)
    if srv is None:
        print("错误：找不到可用端口。请关闭占用端口的程序后重试。")
        input("按回车退出…")
        return

    url = f"http://127.0.0.1:{port}"
    print("=" * 52)
    print("  代码转换器 已启动")
    print(f"  请使用浏览器打开: {url}")
    print("  关闭本窗口即可退出程序")
    print("=" * 52)

    def open_browser():
        time.sleep(0.6)
        webbrowser.open(url)

    if not args.no_browser:
        threading.Thread(target=open_browser, daemon=True).start()

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出。")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
