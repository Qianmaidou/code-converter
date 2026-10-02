# -*- coding: utf-8 -*-
"""求和类代码变体排查：转换 + 运行验证"""
import io, sys, os, tempfile, subprocess, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import rule_engine

RUN = {
    "c":   lambda f, s: subprocess.run(["gcc", f, "-o", f + ".exe", "-O2", "-Wall", "-lm"], capture_output=True, timeout=30).returncode == 0 and subprocess.run([f + ".exe"], input=s.encode(), capture_output=True, timeout=10).returncode == 0,
    "cpp": lambda f, s: subprocess.run(["g++", f, "-o", f + ".exe", "-O2", "-Wall", "-lm"], capture_output=True, timeout=30).returncode == 0 and subprocess.run([f + ".exe"], input=s.encode(), capture_output=True, timeout=10).returncode == 0,
    "python": lambda f, s: subprocess.run([sys.executable, f], input=s.encode(), capture_output=True, timeout=10).returncode == 0,
    "javascript": lambda f, s: subprocess.run(["node", f], input=s.encode(), capture_output=True, timeout=10).returncode == 0,
}
EXT = {"c": "c", "cpp": "cpp", "python": "py", "javascript": "js"}

def check(src, src_lang, dst_lang, stdin="5\n"):
    ok, out = rule_engine.convert(src, src_lang, dst_lang)
    if not ok:
        return f"转换失败: {out}"
    d = tempfile.mkdtemp(prefix="sumvar_")
    f = os.path.join(d, "t." + EXT[dst_lang])
    with open(f, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    rc, run_out = None, ""
    try:
        run_ok = RUN[dst_lang](f, stdin)
    except Exception as e:
        return f"运行异常: {e}\n--- 转换结果 ---\n{out}"
    if not run_ok:
        return f"运行失败\n--- 转换结果 ---\n{out}"
    return None  # 成功

cases = []

# --- C 求和的常见变体 → Python ---
cases.append(("C 标准模板求和→Py", "c", "python",
'''#include <stdio.h>
int main() {
    int n, sum = 0;
    printf("请输入n: ");
    scanf("%d", &n);
    for (int i = 1; i <= n; i++) {
        sum += i;
    }
    printf("和 = %d\\n", sum);
    return 0;
}
'''))
cases.append(("C 先声明i再for→Py", "c", "python",
'''#include <stdio.h>
int main() {
    int n, i, sum = 0;
    printf("请输入n: ");
    scanf("%d", &n);
    for (i = 1; i <= n; i++) {
        sum += i;
    }
    printf("和 = %d\\n", sum);
    return 0;
}
'''))
cases.append(("C int sum=0,i 合并声明→Py", "c", "python",
'''#include <stdio.h>
int main() {
    int n, sum = 0, i;
    scanf("%d", &n);
    for (i = 1; i <= n; i++)
        sum += i;
    printf("%d\\n", sum);
    return 0;
}
'''))
cases.append(("C while循环求和→Py", "c", "python",
'''#include <stdio.h>
int main() {
    int n, i = 1, sum = 0;
    scanf("%d", &n);
    while (i <= n) {
        sum += i;
        i++;
    }
    printf("%d\\n", sum);
    return 0;
}
'''))
cases.append(("C 固定1..10无输入→Py", "c", "python",
'''#include <stdio.h>
int main() {
    int sum = 0;
    for (int i = 1; i <= 10; i++) {
        sum += i;
    }
    printf("%d\\n", sum);
    return 0;
}
'''))
cases.append(("C 求和→JS", "c", "javascript",
'''#include <stdio.h>
int main() {
    int n, sum = 0;
    scanf("%d", &n);
    for (int i = 1; i <= n; i++) {
        sum += i;
    }
    printf("sum=%d\\n", sum);
    return 0;
}
'''))

# --- C++ 求和 → Python ---
cases.append(("C++ cin求和→Py", "cpp", "python",
'''#include <iostream>
using namespace std;
int main() {
    int n, sum = 0;
    cin >> n;
    for (int i = 1; i <= n; i++) {
        sum += i;
    }
    cout << "sum=" << sum << endl;
    return 0;
}
'''))

# --- Python 求和 → C ---
cases.append(("Py for求和→C", "python", "c",
'''n = int(input())
s = 0
for i in range(1, n + 1):
    s += i
print("sum=", s)
'''))
cases.append(("Py while求和→C", "python", "c",
'''n = int(input())
s = 0
i = 1
while i <= n:
    s += i
    i += 1
print(s)
'''))
cases.append(("Py sum(range)→C", "python", "c",
'''n = int(input())
print(sum(range(1, n + 1)))
'''))
cases.append(("Py 无输入固定求和→C", "python", "c",
'''s = 0
for i in range(1, 11):
    s += i
print(s)
'''))
cases.append(("Py for求和→JS", "python", "javascript",
'''n = int(input())
s = 0
for i in range(1, n + 1):
    s += i
print("sum=", s)
'''))

# --- JS 求和 → Python ---
cases.append(("JS let求和→Py", "javascript", "python",
'''let n = 5;
let s = 0;
for (let i = 1; i <= n; i++) {
    s += i;
}
console.log("sum=" + s);
'''))
cases.append(("JS const+循环→Py", "javascript", "python",
'''const n = 10;
let sum = 0;
for (let i = 1; i <= n; i++) {
    sum = sum + i;
}
console.log(`1..${n} sum=${sum}`);
'''))

fails = 0
for name, sl, dl, code in cases:
    res = check(code, sl, dl)
    tag = "✅" if res is None else "❌"
    if res: fails += 1
    print(f"{tag} {name}")
    if res:
        print(res)

print("=" * 50)
print(f"失败 {fails}/{len(cases)}")
