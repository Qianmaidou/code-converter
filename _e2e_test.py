# -*- coding: utf-8 -*-
"""端到端验证：转换 -> 实际运行 -> 对比输出"""
import sys, os, io, subprocess, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import rule_engine as r

PY = sys.executable
GCC = "gcc"
NODE = "node"


def run(args, stdin_data="", timeout=15):
    try:
        p = subprocess.run(args, input=stdin_data.encode("utf-8"),
                           capture_output=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")
    except Exception as e:
        return -1, str(e)


def test_convert_and_run(src_lang, dst_lang, code, stdin_data="", compile_cmd=None, run_cmd=None, label=""):
    ok, conv = r.convert(code, src_lang, dst_lang)
    print("=" * 66)
    print(f"[{src_lang} -> {dst_lang}] {label}  转换{'成功' if ok else '失败'}")
    if not ok:
        print(conv)
        return
    with tempfile.TemporaryDirectory() as td:
        if dst_lang == "python":
            f = os.path.join(td, "t.py")
            open(f, "w", encoding="utf-8").write(conv)
            rc, out = run([PY, f], stdin_data)
        elif dst_lang == "javascript":
            f = os.path.join(td, "t.js")
            open(f, "w", encoding="utf-8").write(conv)
            rc, out = run([NODE, f], stdin_data)
        elif dst_lang in ("c", "cpp"):
            ext = "c" if dst_lang == "c" else "cpp"
            f = os.path.join(td, f"t.{ext}")
            exe = os.path.join(td, "t.exe")
            open(f, "w", encoding="utf-8").write(conv)
            rc, out = run([GCC, f, "-o", exe, "-O2", "-Wall", "-lm"])
            if rc != 0:
                print("编译失败:\n" + out)
                print("---- 转换结果 ----\n" + conv)
                return
            rc, out = run([exe], stdin_data)
        print(f"退出码 {rc}")
        print(out)
        print("---- 转换结果 ----")
        print(conv[:1500])


# 1. C 程序 -> Python，运行对比（含 scanf 输入）
c_code = """#include <stdio.h>
int main() {
    int n, sum = 0;
    printf("请输入n: ");
    scanf("%d", &n);
    for (int i = 1; i <= n; i++) {
        sum += i;
    }
    printf("1..%d 的和 = %d\\n", n, sum);
    return 0;
}
"""
test_convert_and_run("c", "python", c_code, stdin_data="5\n", label="C源程序->Python运行")

# 2. C 程序 -> JS，运行对比
test_convert_and_run("c", "javascript", c_code, stdin_data="5\n", label="C源程序->JS运行")

# 3. C++ 程序 -> Python，运行对比
cpp_code = """#include <iostream>
using namespace std;
int add(int a, int b) { return a + b; }
int main() {
    int x, y;
    cin >> x >> y;
    cout << x << " + " << y << " = " << add(x, y) << endl;
    return 0;
}
"""
test_convert_and_run("cpp", "python", cpp_code, stdin_data="3 7\n", label="C++源程序->Python运行")

# 4. Python 程序 -> C，编译运行对比
py_code = """n = int(input())
s = 0
for i in range(1, n + 1):
    s += i
print("sum =", s)
"""
test_convert_and_run("python", "c", py_code, stdin_data="6\n", label="Python源程序->C编译运行")

# 5. Python 程序 -> JS，运行对比
test_convert_and_run("python", "javascript", py_code, stdin_data="6\n", label="Python源程序->JS运行")

# 6. JS 程序 -> Python，运行对比
js_code = """const fs = require('fs');
let n = 4;
let s = 0;
for (let i = 1; i <= n; i++) {
    s += i;
}
console.log(`sum=${s}`);
"""
test_convert_and_run("javascript", "python", js_code, label="JS源程序->Python运行")
