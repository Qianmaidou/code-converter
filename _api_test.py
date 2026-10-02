# -*- coding: utf-8 -*-
"""server API 测试"""
import json, sys, os, io, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8765"


def post(path, data):
    req = urllib.request.Request(BASE + path, data=json.dumps(data).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


print("=== /api/env ===")
env = get("/api/env")
print({k: v["available"] for k, v in env.items()})

print("\n=== /api/run C (含 scanf) ===")
c_code = '''#include <stdio.h>
int main() {
    int n, sum = 0;
    printf("请输入n: ");
    scanf("%d", &n);
    for (int i = 1; i <= n; i++) sum += i;
    printf("和 = %d\\n", sum);
    return 0;
}
'''
r = post("/api/run", {"lang": "c", "code": c_code, "stdin": "5\n"})
print("ok:", r.get("ok"), "exit:", r.get("exit_code"), "ms:", r.get("elapsed_ms"))
print(r.get("output"))

print("\n=== /api/run JS ===")
r = post("/api/run", {"lang": "javascript", "code": "console.log('hello', 1+2);"})
print("ok:", r.get("ok"), "exit:", r.get("exit_code"))
print(r.get("output"))

print("\n=== /api/run C++ ===")
r = post("/api/run", {"lang": "cpp", "code": '#include <iostream>\nint main(){ int a,b; std::cin>>a>>b; std::cout << a+b << std::endl; return 0; }', "stdin": "3 4\n"})
print("ok:", r.get("ok"), "exit:", r.get("exit_code"))
print(r.get("output"))

print("\n=== /api/convert C->Python ===")
r = post("/api/convert", {"source": c_code, "from": "c", "to": "python"})
print("ok:", r.get("ok"), "engine:", r.get("engine"))
print((r.get("code") or r.get("error"))[:300])

print("\n=== /api/convert Python->C ===")
r = post("/api/convert", {"source": "n = int(input())\nfor i in range(n):\n    print(i*i)", "from": "python", "to": "c"})
print("ok:", r.get("ok"))
print((r.get("code") or r.get("error"))[:300])

print("\n=== /api/convert_ai 未配置 ===")
r = post("/api/convert_ai", {"source": "x=1", "from": "python", "to": "c"})
print("ok:", r.get("ok"), "error:", r.get("error"))

print("\n=== 静态首页 ===")
try:
    with urllib.request.urlopen(BASE + "/", timeout=10) as resp:
        print("status:", resp.status, "len:", len(resp.read()))
except Exception as e:
    print("首页读取失败（预期，界面尚未创建）:", e)

print("\n=== 目录穿越防护 ===")
try:
    with urllib.request.urlopen(BASE + "/../server.py", timeout=10) as resp:
        print("意外成功:", resp.status)
except Exception as e:
    print("已拦截:", type(e).__name__)
