# -*- coding: utf-8 -*-
"""规则引擎自测"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import rule_engine as r

CASES = [
    ("c", "python", "基础 C -> Python（printf/scanf/for）", """#include <stdio.h>
int main() {
    int n, sum = 0;
    printf("请输入一个整数: ");
    scanf("%d", &n);
    for (int i = 1; i <= n; i++) {
        sum += i;
    }
    printf("1到%d的和 = %d\\n", n, sum);
    return 0;
}"""),
    ("c", "python", "C -> Python（数组+if 单行）", """#include <stdio.h>
int main() {
    int arr[5] = {3, 1, 4, 1, 5};
    int i, max = arr[0];
    for (i = 1; i < 5; i++) {
        if (arr[i] > max) max = arr[i];
    }
    printf("max = %d\\n", max);
    return 0;
}"""),
    ("c", "python", "C -> Python（函数+多参数）", """#include <stdio.h>
int add(int a, int b) {
    return a + b;
}
int main() {
    int x = 3, y = 5;
    printf("%d + %d = %d\\n", x, y, add(x, y));
    return 0;
}"""),
    ("cpp", "python", "C++ -> Python（cin/cout）", """#include <iostream>
using namespace std;
int add(int a, int b) {
    return a + b;
}
int main() {
    int x, y;
    cin >> x >> y;
    cout << "sum = " << add(x, y) << endl;
    return 0;
}"""),
    ("c", "javascript", "C -> JS（输入输出）", """#include <stdio.h>
int main() {
    int n;
    printf("请输入n: ");
    scanf("%d", &n);
    for (int i = 0; i < n; i++) {
        printf("%d ", i * i);
    }
    printf("\\n");
    return 0;
}"""),
    ("c", "javascript", "C -> JS（函数+数组）", """#include <stdio.h>
int sum_arr(int arr[], int n) {
    int s = 0;
    for (int i = 0; i < n; i++) s += arr[i];
    return s;
}
int main() {
    int a[] = {1, 2, 3, 4};
    printf("sum = %d\\n", sum_arr(a, 4));
    return 0;
}"""),
    ("python", "c", "Python -> C（脚本式）", """n = int(input())
s = 0
for i in range(1, n + 1):
    s += i
print("sum =", s)
"""),
    ("python", "c", "Python -> C（def main + 守卫）", """def main():
    a = 5
    b = 3
    print(a + b)

if __name__ == "__main__":
    main()
"""),
    ("python", "javascript", "Python -> JS（输入+循环）", """x = int(input())
for i in range(x):
    print(i * i)
"""),
    ("python", "javascript", "Python -> JS（函数+条件）", """def is_even(n):
    if n % 2 == 0:
        return True
    else:
        return False

for i in range(5):
    if is_even(i):
        print(i, "even")
"""),
    ("javascript", "python", "JS -> Python（循环）", """const fs = require('fs');
function _inInt() { return 42; }
let n = _inInt();
let s = 0;
for (let i = 1; i <= n; i++) {
    s += i;
}
console.log(`sum=${s}`);
"""),
]

fails = 0
for src, dst, title, code in CASES:
    print("=" * 64)
    print(f"[{src} -> {dst}] {title}")
    ok, res = r.convert(code, src, dst)
    if not ok:
        fails += 1
        print("FAIL: " + res)
    else:
        print(res)
print("=" * 64)
print(f"通过 {len(CASES) - fails}/{len(CASES)}")
