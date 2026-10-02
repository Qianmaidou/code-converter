# -*- coding: utf-8 -*-
"""
代码转换规则引擎（离线版）
在 C / C++ / Python / JavaScript 之间转换常见语法结构：
变量声明、输入输出（printf/scanf/cout/cin/print/input/console.log）、
循环、条件、函数、数组/列表、常用库函数等。

适合教材与作业级别的代码；复杂代码建议使用软件内的「AI 转换」。
输出为“尽力转换 + 关键注释提示”，请人工核对后再使用。
"""

import re

# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

TYPE_TOKENS = {
    "const", "static", "volatile", "register", "unsigned", "signed",
    "long", "short", "int", "char", "float", "double", "void", "bool",
    "auto", "size_t", "wchar_t", "string", "FILE", "struct", "enum",
    "union", "std::string", "vector", "list", "map", "set", "pair",
    "int64_t", "uint64_t", "int32_t", "uint32_t", "int16_t", "uint16_t",
    "int8_t", "uint8_t", "intptr_t", "uintptr_t", "extern", "inline",
}

LOOP_VAR_TYPES = (
    r"(?:(?:const|static|volatile|register|unsigned|signed|long|short|"
    r"int|char|float|double|bool|auto|size_t)\s+)*"
)


def split_top(s, sep=","):
    """在顶层（括号/引号外）按分隔符切分"""
    parts, depth, cur = [], 0, ""
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch in "\"'":
            quote = ch
            cur += ch
            i += 1
            while i < n and s[i] != quote:
                if s[i] == "\\" and i + 1 < n:
                    cur += s[i:i + 2]
                    i += 2
                    continue
                cur += s[i]
                i += 1
            if i < n:
                cur += s[i]
                i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    parts.append(cur)
    return [p.strip() for p in parts]


def split_cond(s):
    """按顶层分号切分 for(...) 的三个部分"""
    return split_top(s, ";")


def split_multi(s, sep):
    """按多字符分隔符在顶层切分（如 <<、>>）"""
    parts, depth, cur = [], 0, ""
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch in "\"'":
            quote = ch
            cur += ch
            i += 1
            while i < n and s[i] != quote:
                if s[i] == "\\" and i + 1 < n:
                    cur += s[i:i + 2]
                    i += 2
                    continue
                cur += s[i]
                i += 1
            if i < n:
                cur += s[i]
            i += 1
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if s.startswith(sep, i) and depth == 0:
            parts.append(cur)
            cur = ""
            i += len(sep)
            continue
        cur += ch
        i += 1
    parts.append(cur)
    return [p.strip() for p in parts]


def strip_comment(line, lang):
    """去掉行尾注释，返回 (主体, 注释)"""
    marker = "//" if lang != "python" else "#"
    out, i, n = [], 0, len(line)
    while i < n:
        ch = line[i]
        if ch in "\"'":
            quote = ch
            j = i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == quote:
                    break
                j += 1
            out.append(line[i:min(j + 1, n)])
            i = min(j + 1, n)
        elif line.startswith(marker, i):
            return "".join(out).rstrip(), line[i + len(marker):].strip()
        else:
            out.append(ch)
            i += 1
    return "".join(out).rstrip(), ""


def strip_block_comments(code):
    """去掉 C 系块注释 /* */，返回 (代码, 注释行列表)"""
    out = []
    notes = []
    i, n = 0, len(code)
    while i < n:
        if code.startswith("/*", i):
            j = code.find("*/", i + 2)
            if j == -1:
                j = n
            block = code[i:j + 2]
            for ln in block.splitlines():
                t = ln.strip().strip("*/").strip()
                if t:
                    notes.append(t)
            i = j + 2
        else:
            out.append(code[i])
            i += 1
    return "".join(out), notes


def join_lines(lines):
    res = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                res.append("")
            continue
        blank = 0
        res.append(ln.rstrip())
    while res and not res[-1].strip():
        res.pop()
    return "\n".join(res)


def esc_fstring(s):
    return s.replace("{", "{{").replace("}", "}}")


def esc_js_template(s):
    return s.replace("`", "\\`").replace("${", "\\${")


# ---------------------------------------------------------------------------
# 表达式运算符映射
# ---------------------------------------------------------------------------

def map_ops_c_to_py(expr):
    s = expr
    s = re.sub(r"\btrue\b", "True", s)
    s = re.sub(r"\bfalse\b", "False", s)
    s = re.sub(r"\bNULL\b", "None", s)
    s = re.sub(r"\bnullptr\b", "None", s)
    s = re.sub(r"&&", " and ", s)
    s = re.sub(r"\|\|", " or ", s)
    s = re.sub(r"!=", " != ", s)
    s = re.sub(r"==", " == ", s)
    s = re.sub(r"<=", " <= ", s)
    s = re.sub(r">=", " >= ", s)
    s = re.sub(r"!\s*(\w)", r"not \1", s)
    s = re.sub(r"!\s*\(", r"not (", s)
    s = re.sub(r"(\w)\+\+", r"\1 += 1", s)
    s = re.sub(r"\+\+(\w)", r"\1 += 1", s)
    s = re.sub(r"(\w)--", r"\1 -= 1", s)
    s = re.sub(r"--(\w)", r"\1 -= 1", s)
    return s.strip()


def map_ops_c_to_js(expr):
    s = re.sub(r"\bNULL\b", "null", expr)
    s = re.sub(r"\bnullptr\b", "null", s)
    return s.strip()


def map_ops_py_to_c(expr):
    s = expr
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    s = re.sub(r"\bNone\b", "NULL", s)
    s = re.sub(r"\band\b", " && ", s)
    s = re.sub(r"\bor\b", " || ", s)
    s = re.sub(r"!\s*=", " != ", s)
    s = re.sub(r"not\s+(\w)", r"!\1", s)
    s = re.sub(r"not\s*\(", r"!(", s)
    return s.strip()


def map_ops_py_to_js(expr):
    s = expr
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    s = re.sub(r"\bNone\b", "null", s)
    s = re.sub(r"\band\b", " && ", s)
    s = re.sub(r"\bor\b", " || ", s)
    s = re.sub(r"not\s+(\w)", r"!\1", s)
    s = re.sub(r"not\s*\(", r"!(", s)
    return s.strip()


def map_ops_js_to_py(expr):
    s = expr
    s = re.sub(r"\btrue\b", "True", s)
    s = re.sub(r"\bfalse\b", "False", s)
    s = re.sub(r"\bnull\b", "None", s)
    s = re.sub(r"\bundefined\b", "None", s)
    s = re.sub(r"&&", " and ", s)
    s = re.sub(r"\|\|", " or ", s)
    s = re.sub(r"===", " == ", s)
    s = re.sub(r"!==", " != ", s)
    s = re.sub(r"\b(?:let|var|const)\s+(\w+)", r"\1", s)
    return s.strip()


def js_concat_to_py_fstring(expr):
    """JS 表达式中的 '字符串' + 变量 拼接 -> Python f-string。
    纯变量加法（a + b）保持不变；只要有一个操作数是字符串字面量就整体转 f-string。"""
    tokens = [t.strip() for t in split_top(expr, "+") if t.strip()]
    if len(tokens) < 2:
        return map_ops_js_to_py(expr)
    has_str = False
    for t in tokens:
        if (t.startswith('"') and t.endswith('"') and len(t) >= 2) or \
           (t.startswith("'") and t.endswith("'") and len(t) >= 2):
            has_str = True
            break
    if not has_str:
        return map_ops_js_to_py(expr)
    pieces = []
    for t in tokens:
        t = t.strip()
        if t.startswith('"') and t.endswith('"') and len(t) >= 2:
            pieces.append(t[1:-1].replace("{", "{{").replace("}", "}}"))
        elif t.startswith("'") and t.endswith("'") and len(t) >= 2:
            pieces.append(t[1:-1].replace("{", "{{").replace("}", "}}"))
        else:
            pieces.append("{" + map_ops_js_to_py(t) + "}")
    return 'f"' + "".join(pieces) + '"'


# ---------------------------------------------------------------------------
# 格式化字符串解析
# ---------------------------------------------------------------------------

SPEC_RE = re.compile(r"%(\d*\.?\d*)([diufFscxXopgeG%])")


def split_format(fmt):
    out = []
    i, n = 0, len(fmt)
    while i < n:
        if fmt[i] == "%" and i + 1 < n:
            m = SPEC_RE.match(fmt, i)
            if m:
                if m.group(2) == "%":
                    out.append(("text", "%"))
                else:
                    out.append(("spec", m.group(1), m.group(2)))
                i = m.end()
                continue
        out.append(("text", fmt[i]))
        i += 1
    return out


def fmt_to_python(fmt, args):
    """C printf 格式串 + 参数 -> Python print(f...) 语句"""
    parts = split_format(fmt)
    pieces = []
    ai = 0
    for p in parts:
        if p[0] == "text":
            pieces.append(esc_fstring(p[1]))
        else:
            _w, typ = p[1], p[2]
            arg = args[ai].lstrip("&").strip() if ai < len(args) else "?"
            ai += 1
            if typ in ("x", "X"):
                pieces.append("{" + arg + ":#x}")
            elif typ == "o":
                pieces.append("{" + arg + ":o}")
            else:
                pieces.append("{" + arg + "}")
    if not any(p[0] == "spec" for p in parts):
        text = "".join(p[1] for p in parts if p[0] == "text")
        if text == "\\n":
            return "print()"
        if text.endswith("\\n"):
            return f'print("{text[:-2]}")'
        return f'print("{text}", end="")'
    body = "".join(pieces)
    if not body:
        return "print()"
    if body.endswith("\\n"):
        body = body[:-2]
        return f'print(f"{body}")'
    return f'print(f"{body}", end="")'


def fmt_to_js(fmt, args):
    """C printf 格式串 + 参数 -> JS console.log(模板字符串)"""
    parts = split_format(fmt)
    pieces = []
    ai = 0
    for p in parts:
        if p[0] == "text":
            pieces.append(esc_js_template(p[1]))
        else:
            _w, typ = p[1], p[2]
            arg = args[ai].lstrip("&").strip() if ai < len(args) else "?"
            ai += 1
            if typ in ("d", "i", "u", "x", "X", "o", "f", "lf", "s", "c", "g", "e", "G", "E"):
                pieces.append("${" + arg + "}")
            else:
                pieces.append("${" + arg + "}")
    body = "".join(pieces)
    if not body:
        return "console.log();"
    return f"console.log(`{body}`);"


# ---------------------------------------------------------------------------
# C 声明解析
# ---------------------------------------------------------------------------

def parse_c_decls(line):
    """解析 C/C++ 变量声明行，支持多声明：int a = 1, b[3], *p; 失败返回 None"""
    m = re.match(
        r"^\s*((?:[A-Za-z_][\w:]*|std::[A-Za-z_][\w:]*|<[^>]*>|[&*]|\s)+?)\s*(.+?);?\s*$",
        line,
    )
    if not m:
        return None
    type_part, rest = m.group(1), m.group(2)
    tokens = re.findall(r"[A-Za-z_][\w:]*|<[^>]*>", type_part)
    remain = type_part
    for t in tokens:
        if t in TYPE_TOKENS or re.fullmatch(r"<[^>]*>", t):
            remain = remain.replace(t, "", 1)
    remain = remain.replace("*", "").replace("&", "").strip()
    if remain:
        return None
    decls = []
    for part in split_top(rest):
        pm = re.match(
            r"^[&*]*\s*([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*(?:=\s*(.+))?$",
            part.strip(),
        )
        if not pm:
            return None
        init = (pm.group(3) or "").strip() or None
        decls.append({"name": pm.group(1), "arr": pm.group(2), "init": init, "tokens": tokens})
    return decls


def c_type_of(d):
    toks = d.get("tokens", [])
    if any(t in ("vector", "list", "map", "set", "pair") or "<" in t for t in toks):
        return "list"
    if "string" in toks or "std::string" in toks:
        return "str"
    if "char" in toks:
        return "str" if d["arr"] or (d["init"] and d["init"].startswith('"')) else "char"
    if "float" in toks or "double" in toks:
        return "float"
    if "bool" in toks:
        return "bool"
    if "FILE" in toks:
        return "file"
    return "int"


def c_array_init(init):
    if init and init.startswith("{") and init.endswith("}"):
        return "[" + init[1:-1].strip() + "]"
    return None


def cpp_list_ctor(init):
    if init and re.fullmatch(r"\(\s*(\d+)\s*\)", init):
        n = re.search(r"\d+", init).group()
        return f"[0] * {n}"
    return None


# ---------------------------------------------------------------------------
# 符号表（做类型推断，辅助 cin/cout / print 转换）
# ---------------------------------------------------------------------------

class SymTable:
    def __init__(self):
        self.vars = {}

    def declare(self, name, typ, init=None):
        self.vars[name] = typ
        if init is not None:
            t = guess_type(init)
            if t:
                self.vars[name] = t

    def assign(self, name, rhs):
        if name in self.vars and self.vars[name] != "char":
            return
        t = guess_type(rhs)
        if t:
            self.vars[name] = t

    def get(self, name):
        return self.vars.get(name, "int")


def guess_type(rhs):
    r = rhs.strip()
    if not r:
        return None
    if r.startswith('"') or r.startswith("'"):
        return "str"
    if r.startswith("["):
        return "list"
    if r in ("True", "False", "true", "false"):
        return "bool"
    if r in ("None", "NULL", "null"):
        return None
    if re.fullmatch(r"-?\d+", r):
        return "int"
    if re.fullmatch(r"-?\d*\.\d+([eE][+-]?\d+)?|-?\d+[eE][+-]?\d+", r):
        return "float"
    return None


# ---------------------------------------------------------------------------
# C / C++ -> Python
# ---------------------------------------------------------------------------

def clike_to_python(code, is_cpp=False):
    code, block_notes = strip_block_comments(code)
    lines = code.splitlines()
    out = []
    depth = 0
    sym = SymTable()
    do_while = 0
    needs_math = "#include <math.h>" in code
    needs_random = "#include <stdlib.h>" in code or "#include <time.h>" in code
    saw_main = False
    preprocessor = []
    switch_depth = 0

    def emit(s, d=None):
        out.append(" " * (4 * (depth if d is None else d)) + s)

    for raw in lines:
        if not raw.strip():
            out.append("")
            continue
        line, comment = strip_comment(raw, "c")
        s = line.strip()
        if not s:
            if comment:
                emit("# " + comment)
            continue
        if s.startswith("#"):
            m = re.match(r"#\s*define\s+([A-Za-z_]\w*)\s+(.+)", s)
            if m:
                preprocessor.append(f"{m.group(1)} = {m.group(2)}")
            continue
        if s.startswith("using namespace"):
            continue
        # 去掉行尾 { 与 ;
        if s.endswith("{"):
            s = s[:-1].rstrip()
        if s.endswith(";"):
            s = s[:-1].rstrip()

        # do { } while(cond);
        if re.match(r"^do\s*$", s):
            emit("while True:")
            depth += 1
            do_while = depth
            continue
        m_dowhile = re.match(r"^}\s*while\s*\((.*)\)\s*;?$", s)
        if m_dowhile and do_while:
            depth = max(0, depth - 1)
            cond = map_ops_c_to_py(m_dowhile.group(1))
            emit(f"if not ({cond}):")
            depth += 1
            emit("    break")
            depth -= 1
            do_while = 0
            continue

        # } else if / } else
        m_else = re.match(r"^\}\s*else\s*(if\s*\((.*)\))?\s*$", s, re.S)
        if m_else:
            depth = max(0, depth - 1)
            if m_else.group(2) is not None:
                emit(f"elif {map_ops_c_to_py(m_else.group(2))}:")
            else:
                emit("else:")
            depth += 1
            continue
        if s == "}":
            depth = max(0, depth - 1)
            if switch_depth and depth < switch_depth:
                switch_depth = 0
            continue

        # 单行函数：int add(int a, int b) { return a + b; }
        m_func1 = re.match(
            r"^\s*((?:[A-Za-z_][\w:]*|<[^>]*>|::|[&*]|\s)+?)\s*([A-Za-z_]\w*)\s*\((.*)\)\s*\{\s*(.+?)\}\s*$",
            s,
        )
        if m_func1 and not re.match(r"^(if|for|while|switch|return)\s*\(", s):
            type_part, fname, params, body = m_func1.groups()
            toks = re.findall(r"[A-Za-z_][\w:]*|<[^>]*>", type_part)
            if any(t in TYPE_TOKENS for t in toks):
                plist = []
                for p in split_top(params):
                    if not p or p in ("void", "void "):
                        continue
                    pm = re.match(
                        r"^(?:const\s+)?((?:[A-Za-z_][\w:]*|<[^>]*>|std::\w+)"
                        r"(?:\s*[&*])*)\s*([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*"
                        r"(?:=\s*(.+))?$",
                        p,
                    )
                    if pm:
                        pname = pm.group(2)
                        pinit = pm.group(3)
                        sym.declare(pname, "int", pinit)
                        plist.append(f"{pname}={pinit}" if pinit else pname)
                    else:
                        p0 = re.sub(r"\[.*", "", p.replace("&", "").replace("*", "").strip())
                        plist.append(p0.split()[-1] if p0.split() else p0)
                body_py = map_ops_c_to_py(re.sub(r"\s*;?\s*$", "", body))
                if fname == "main":
                    saw_main = True
                    emit("def main():")
                    depth += 1
                    emit(body_py)
                    depth -= 1
                else:
                    emit(f"def {fname}({', '.join(plist)}):")
                    depth += 1
                    emit(body_py)
                    depth -= 1
                continue

        # 函数定义
        m_func = re.match(
            r"^\s*((?:[A-Za-z_][\w:]*|<[^>]*>|::|[&*]|\s)+?)\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$",
            s,
        )
        is_ctrl = re.match(r"^(if|for|while|switch|return)\s*\(", s)
        if m_func and not is_ctrl:
            type_part, fname, params = m_func.group(1), m_func.group(2), m_func.group(3)
            toks = re.findall(r"[A-Za-z_][\w:]*|<[^>]*>", type_part)
            real_type = [t for t in toks if t in TYPE_TOKENS]
            if real_type:
                if fname == "main":
                    saw_main = True
                    if out and out[-1].strip():
                        out.append("")
                    emit("def main():")
                    depth += 1
                    continue
                plist = []
                for p in split_top(params):
                    if not p or p in ("void", "void "):
                        continue
                    pm = re.match(
                        r"^(?:const\s+)?((?:[A-Za-z_][\w:]*|<[^>]*>|std::\w+)"
                        r"(?:\s*[&*])*)\s*([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*"
                        r"(?:=\s*(.+))?$",
                        p,
                    )
                    if pm:
                        pname = pm.group(2)
                        pinit = pm.group(3)
                        sym.declare(pname, "int", pinit)
                        plist.append(f"{pname}={pinit}" if pinit else pname)
                    else:
                        p0 = re.sub(r"\[.*", "", p.replace("&", "").replace("*", "").strip())
                        pname = p0.split()[-1] if p0.split() else p0
                        plist.append(pname)
                if out and out[-1].strip():
                    out.append("")
                emit(f"def {fname}({', '.join(plist)}):")
                depth += 1
                continue

        # if / while / switch
        m_if = re.match(r"^if\s*\((.*)\)\s*$", s, re.S)
        if m_if:
            emit(f"if {map_ops_c_to_py(m_if.group(1))}:")
            depth += 1
            continue
        m_if1 = re.match(r"^if\s*\((.*)\)\s+(.+)$", s)
        if m_if1:
            emit(f"if {map_ops_c_to_py(m_if1.group(1))}: {map_ops_c_to_py(m_if1.group(2).rstrip(';'))}")
            continue
        m_while = re.match(r"^while\s*\((.*)\)\s*$", s, re.S)
        if m_while:
            emit(f"while {map_ops_c_to_py(m_while.group(1))}:")
            depth += 1
            continue
        m_while1 = re.match(r"^while\s*\((.*)\)\s+(.+)$", s)
        if m_while1:
            emit(f"while {map_ops_c_to_py(m_while1.group(1))}: {map_ops_c_to_py(m_while1.group(2).rstrip(';'))}")
            continue
        m_switch = re.match(r"^switch\s*\((.*)\)\s*$", s, re.S)
        if m_switch:
            emit(f"_sw = {map_ops_c_to_py(m_switch.group(1))}")
            emit("if False:")
            depth += 1
            switch_depth = depth
            continue
        m_case = re.match(r"^case\s+(.+?)\s*:\s*$", s)
        if m_case:
            depth = max(0, depth - 1)
            emit(f"elif _sw == {map_ops_c_to_py(m_case.group(1))}:")
            depth += 1
            continue
        if re.match(r"^default\s*:\s*$", s):
            depth = max(0, depth - 1)
            emit("else:")
            depth += 1
            continue

        # for
        m_for = re.match(r"^for\s*\((.*)\)\s*$", s, re.S)
        if m_for:
            parts = split_cond(m_for.group(1))
            if len(parts) == 3:
                r = c_for_to_range(parts[0], parts[1], parts[2])
                if r:
                    emit(f"for {r}:")
                    depth += 1
                    continue
                emit("# for 循环未能自动转换，请人工调整")
                emit(f"# for ({'; '.join(parts)})")
                depth += 1
                continue
            m_rf = re.match(
                LOOP_VAR_TYPES + r"([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*$",
                m_for.group(1).strip(),
            )
            if m_rf:
                emit(f"for {m_rf.group(1)} in {m_rf.group(2)}:")
                depth += 1
                continue
            emit("# for 循环未能自动转换，请人工调整")
            depth += 1
            continue

        # 单行 for：for (i=0;i<n;i++) stmt;
        m_for1 = re.match(r"^for\s*\((.*)\)\s+(.+)$", s)
        if m_for1:
            parts = split_cond(m_for1.group(1))
            if len(parts) == 3:
                rr = c_for_to_range(parts[0], parts[1], parts[2])
                if rr:
                    emit(f"for {rr}: {map_ops_c_to_py(m_for1.group(2).rstrip(';'))}")
                    continue
            emit("# for 循环未能自动转换，请人工调整")
            emit(f"# for ({m_for1.group(1)}) {m_for1.group(2)}")
            continue

        # printf / puts / scanf / getchar / putchar
        m_pf = re.match(r"^printf\s*\((.*)\)\s*$", s, re.S)
        if m_pf:
            args = split_top(m_pf.group(1))
            if args and args[0].startswith('"'):
                fmt = args[0][1:-1]
                emit(fmt_to_python(fmt, args[1:]))
            else:
                emit("# printf 参数异常，请人工处理")
            continue
        m_puts = re.match(r"^puts\s*\((.*)\)\s*$", s, re.S)
        if m_puts:
            arg = m_puts.group(1).strip()
            if arg.startswith('"'):
                emit(f'print("{arg[1:-1]}")')
            else:
                emit(f"print({arg})")
            continue
        m_sf = re.match(r"^scanf\s*\((.*)\)\s*$", s, re.S)
        if m_sf:
            args = split_top(m_sf.group(1))
            if args and args[0].startswith('"'):
                fmt = args[0][1:-1]
                specs = [p for p in split_format(fmt) if p[0] == "spec"]
                targets = [a.strip().lstrip("&") for a in args[1:]]
                for st in scanf_to_python(specs, targets):
                    emit(st)
            else:
                emit("# scanf 参数异常，请人工处理")
            continue
        if re.match(r"^getchar\s*\(\s*\)\s*$", s):
            emit("_ch = input()[0]")
            continue
        m_putchar = re.match(r"^putchar\s*\((.*)\)\s*$", s)
        if m_putchar:
            emit(f'print({m_putchar.group(1).strip()}, end="")')
            continue

        # C++ cout / cin / getline
        m_cout = re.match(r"^(?:std::)?cout\s*(.*)$", s)
        if m_cout:
            emit(cpp_cout_to_python(m_cout.group(1)))
            continue
        m_cin = re.match(r"^(?:std::)?cin\s*(.*)$", s)
        if m_cin:
            for st in cpp_cin_to_python(m_cin.group(1), sym):
                emit(st)
            continue
        m_getline = re.match(r"^getline\s*\(\s*(?:std::)?cin\s*,\s*([A-Za-z_]\w*)\s*\)\s*$", s)
        if m_getline:
            emit(f"{m_getline.group(1)} = input()")
            sym.declare(m_getline.group(1), "str")
            continue

        # return
        m_ret = re.match(r"^return\s*(.*)$", s)
        if m_ret:
            if m_ret.group(1).strip() in ("", "0"):
                emit("return 0")
            else:
                emit("return " + map_ops_c_to_py(m_ret.group(1)))
            continue
        if s in ("break", "continue"):
            emit(s)
            continue

        # 声明（含多声明）
        decls = parse_c_decls(s)
        if decls:
            for d in decls:
                name, arr, init = d["name"], d["arr"], d["init"]
                typ = c_type_of(d)
                if arr and not init:
                    n = arr[1:-1]
                    if n == "":
                        emit(f"{name} = []  # 长度未指定")
                    elif n.isdigit():
                        emit(f'{name} = ["", ""] * 0 if typ == "str" else [0] * {n}' if False else
                             (f'{name} = [""] * {n}' if typ == "str" else f"{name} = [0] * {n}"))
                    else:
                        emit(f"{name} = [0] * ({map_ops_c_to_py(n)})")
                    sym.declare(name, "list")
                    continue
                if arr and init:
                    ci = c_array_init(init)
                    if ci:
                        emit(f"{name} = {ci}")
                    elif init == "0" and arr[1:-1]:
                        emit(f"{name} = [0] * ({arr[1:-1]})")
                    else:
                        emit(f"{name} = {map_ops_c_to_py(init)}")
                    sym.declare(name, "list")
                    continue
                ctor = cpp_list_ctor(init) if is_cpp else None
                if ctor:
                    emit(f"{name} = {ctor}")
                    sym.declare(name, "list")
                    continue
                if init is None:
                    if typ == "str":
                        emit(f'{name} = ""')
                    elif typ == "bool":
                        emit(f"{name} = False")
                    elif typ == "list":
                        emit(f"{name} = []")
                    elif typ == "char":
                        emit(f'{name} = ""')
                    elif typ == "file":
                        emit(f"{name} = None")
                    else:
                        emit(f"{name} = 0")
                    sym.declare(name, typ)
                else:
                    init_py = map_ops_c_to_py(init)
                    init_py = re.sub(r"\bgetchar\s*\(\s*\)", "input()[0]", init_py)
                    if typ == "bool":
                        init_py = init_py.replace("true", "True").replace("false", "False")
                    emit(f"{name} = {init_py}")
                    sym.declare(name, typ, init)
            continue

        # 普通语句
        s2 = s
        if is_cpp:
            s2 = re.sub(r"\.push_back\s*\((.+)\)", r".append(\1)", s2)
            s2 = re.sub(r"\.size\s*\(\s*\)", ".__len__()", s2)
            s2 = re.sub(r"\.empty\s*\(\s*\)", ".__len__() == 0", s2)
            s2 = re.sub(r"\.length\s*\(\s*\)", ".__len__()", s2)
            s2 = re.sub(r"\.substr\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)", r"[\1:\1+\2]", s2)
            s2 = re.sub(r"\.at\s*\(", "[", s2)
            m_sort = re.match(
                r"^sort\s*\(([^,]+)\.begin\s*\(\s*\)\s*,\s*\1\.end\s*\(\s*\)\s*\)\s*$", s2
            )
            if m_sort:
                emit(f"{m_sort.group(1)}.sort()")
                continue
        s3 = map_ops_c_to_py(s2)
        s3 = re.sub(r"\bstrlen\s*\(([^)]*)\)", r"len(\1)", s3)
        s3 = re.sub(r"\bstrcmp\s*\(([^,)]+)\s*,\s*([^)]+)\)", r"(\1 == \2)", s3)
        s3 = re.sub(r"\bstrcpy\s*\(([^,)]+)\s*,\s*([^)]+)\)", r"\1 = \2", s3)
        s3 = re.sub(r"\bstrcat\s*\(([^,)]+)\s*,\s*([^)]+)\)", r"\1 = \1 + \2", s3)
        s3 = re.sub(r"\bsqrt\s*\(", "sqrt(", s3)
        s3 = re.sub(r"\bpow\s*\(", "pow(", s3)
        s3 = re.sub(r"\bfabs\s*\(", "fabs(", s3)
        s3 = re.sub(r"\bsrand\s*\([^)]*\)", "None  # srand 已忽略（Python 默认随机种子）", s3)
        s3 = re.sub(r"\brand\s*\(\s*\)\s*%\s*(\d+)", r"randrange(\1)", s3)
        s3 = re.sub(r"\brand\s*\(\s*\)", "random()", s3)
        s3 = re.sub(r"\bsizeof\s*\([^)]*\)", "0  # sizeof 请人工处理", s3)
        emit(s3)

    if saw_main:
        out.append("")
        out.append('if __name__ == "__main__":')
        out.append("    main()")

    header = []
    if preprocessor:
        header.append("# 由 #define 转换的常量")
        header.extend(preprocessor)
    if needs_math or needs_random:
        if needs_math:
            header.append("from math import *")
        if needs_random:
            header.append("from random import *")
    if block_notes:
        header.append("# 原注释：" + "；".join(block_notes[:3]))
    if header:
        out = header + [""] + out
    return join_lines(out)


def c_for_to_range(init, cond, incr):
    m = re.match(LOOP_VAR_TYPES + r"([A-Za-z_]\w*)\s*=\s*(.+)", init)
    if not m:
        return None
    var, start = m.group(1), m.group(2)
    m2 = re.match(rf"^\s*{re.escape(var)}\s*(<=|<|>=|>)\s*(.+?)\s*$", cond)
    if not m2:
        return None
    op, bound = m2.group(1), m2.group(2)
    m3 = re.match(rf"^\s*{re.escape(var)}\s*(\+\+|--|\+=|-=)\s*(\d*)\s*$", incr)
    if not m3:
        return None
    op2, k = m3.group(1), m3.group(2) or "1"
    if op2 in ("++", "--"):
        step = "1" if op2 == "++" else "-1"
    else:
        step = k if op2 == "+=" else f"-{k}"
    start = map_ops_c_to_py(start)
    bound = map_ops_c_to_py(bound)
    if step == "1":
        if op == "<":
            return f"{var} in range({start}, {bound})"
        if op == "<=":
            return f"{var} in range({start}, {bound} + 1)"
        if op == ">":
            return f"{var} in range({start}, {bound}, -1)"
        return f"{var} in range({start}, {bound} - 1, -1)"
    if step.startswith("-"):
        if op == ">":
            return f"{var} in range({start}, {bound}, {step})"
        return f"{var} in range({start}, {bound} - 1, {step})"
    if op == "<":
        return f"{var} in range({start}, {bound}, {step})"
    return f"{var} in range({start}, {bound} + 1, {step})"


def scanf_to_python(specs, targets):
    stmts = []
    if not targets:
        return stmts
    types = [p[2] for p in specs]
    if len(targets) == 1 and len(types) == 1:
        t, var = types[0], targets[0]
        if t == "d":
            stmts.append(f"{var} = int(input())")
        elif t in ("f", "lf"):
            stmts.append(f"{var} = float(input())")
        elif t == "c":
            stmts.append(f"{var} = input()[0]")
        else:
            stmts.append(f"{var} = input()")
        return stmts
    if len(targets) == len(types):
        if all(t == "d" for t in types):
            stmts.append(f"{', '.join(targets)} = map(int, input().split())")
            return stmts
        if all(t in ("f", "lf") for t in types):
            stmts.append(f"{', '.join(targets)} = map(float, input().split())")
            return stmts
    for t, var in zip(types, targets):
        if t == "d":
            stmts.append(f"{var} = int(input())")
        elif t in ("f", "lf"):
            stmts.append(f"{var} = float(input())")
        elif t == "c":
            stmts.append(f"{var} = input()[0]")
        else:
            stmts.append(f"{var} = input()")
    return stmts


def cpp_cout_to_python(rest):
    parts = [p.strip() for p in split_multi(rest, "<<") if p.strip()]
    if not parts:
        return "print()"
    has_end = parts[-1] in ("endl", "std::endl")
    if has_end:
        parts = parts[:-1]
    py_parts = []
    for p in parts:
        if p.startswith('"'):
            py_parts.append(f'"{p[1:-1]}"')
        else:
            py_parts.append(map_ops_c_to_py(p))
    arg_str = ", ".join(py_parts)
    if not arg_str:
        return "print()"
    return f"print({arg_str})" if has_end else f'print({arg_str}, end="")'


def cpp_cin_to_python(rest, sym):
    parts = [p.strip() for p in split_multi(rest, ">>") if p.strip()]
    if not parts:
        return []
    # 多个变量：从同一行读取（与 C++ cin 行为接近）
    if len(parts) > 1:
        types = [sym.get(p) for p in parts]
        if all(t not in ("str", "char") for t in types):
            vars_s = ", ".join(parts)
            return [f"{vars_s} = map(int, input().split())"]
    stmts = []
    for p in parts:
        typ = sym.get(p)
        if typ in ("str", "char"):
            stmts.append(f"{p} = input()")
        elif typ == "float":
            stmts.append(f"{p} = float(input())")
        else:
            stmts.append(f"{p} = int(input())")
    return stmts


# ---------------------------------------------------------------------------
# C / C++ -> JavaScript
# ---------------------------------------------------------------------------

def clike_to_js(code, is_cpp=False):
    code, block_notes = strip_block_comments(code)
    lines = code.splitlines()
    out = []
    depth = 0
    saw_main = False
    needs_input = False
    has_math = "#include <math.h>" in code

    def emit(s, d=None):
        out.append("  " * (depth if d is None else d) + s)

    for raw in lines:
        if not raw.strip():
            out.append("")
            continue
        line, comment = strip_comment(raw, "c")
        s = line.strip()
        if not s:
            if comment:
                emit("// " + comment)
            continue
        if s.startswith("#"):
            continue
        if s.startswith("using namespace"):
            continue
        if s.endswith("{"):
            s = s[:-1].rstrip()
        if s.endswith(";"):
            s = s[:-1].rstrip()

        m_else = re.match(r"^\}\s*else\s*(if\s*\((.*)\))?\s*$", s, re.S)
        if m_else:
            depth = max(0, depth - 1)
            if m_else.group(2) is not None:
                emit(f"else if ({map_ops_c_to_js(m_else.group(2))}) {{")
            else:
                emit("} else {")
            depth += 1
            continue
        if s == "}":
            depth = max(0, depth - 1)
            emit("}")
            continue

        # 单行函数：int add(int a, int b) { return a + b; }
        m_func1 = re.match(
            r"^\s*((?:[A-Za-z_][\w:]*|<[^>]*>|::|[&*]|\s)+?)\s*([A-Za-z_]\w*)\s*\((.*)\)\s*\{\s*(.+?)\}\s*$",
            s,
        )
        if m_func1 and not re.match(r"^(if|for|while|switch|return)\s*\(", s):
            type_part, fname, params, body = m_func1.groups()
            toks = re.findall(r"[A-Za-z_][\w:]*|<[^>]*>", type_part)
            if any(t in TYPE_TOKENS for t in toks):
                plist = []
                for p in split_top(params):
                    if not p or p == "void":
                        continue
                    pm = re.match(
                        r"^(?:const\s+)?((?:[A-Za-z_][\w:]*|<[^>]*>|std::\w+)"
                        r"(?:\s*[&*])*)\s*([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*$",
                        p,
                    )
                    if pm:
                        plist.append(pm.group(2))
                    else:
                        p0 = re.sub(r"\[.*", "", p.replace("&", "").replace("*", "").strip())
                        plist.append(p0.split()[-1] if p0.split() else p0)
                body_js = map_ops_c_to_js(body)
                if fname == "main":
                    saw_main = True
                    emit(f"function main() {{ {body_js} }}")
                else:
                    emit(f"function {fname}({', '.join(plist)}) {{ {body_js} }}")
                continue

        # 函数
        m_func = re.match(
            r"^\s*((?:[A-Za-z_][\w:]*|<[^>]*>|::|[&*]|\s)+?)\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$",
            s,
        )
        is_ctrl = re.match(r"^(if|for|while|switch|return)\s*\(", s)
        if m_func and not is_ctrl:
            type_part, fname, params = m_func.group(1), m_func.group(2), m_func.group(3)
            toks = re.findall(r"[A-Za-z_][\w:]*|<[^>]*>", type_part)
            real_type = [t for t in toks if t in TYPE_TOKENS]
            if real_type:
                if fname == "main":
                    saw_main = True
                    emit("function main() {")
                    depth += 1
                    continue
                plist = []
                for p in split_top(params):
                    if not p or p == "void":
                        continue
                    pm = re.match(
                        r"^(?:const\s+)?((?:[A-Za-z_][\w:]*|<[^>]*>|std::\w+)"
                        r"(?:\s*[&*])*)\s*([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*$",
                        p,
                    )
                    if pm:
                        plist.append(pm.group(2))
                    else:
                        p0 = re.sub(r"\[.*", "", p.replace("&", "").replace("*", "").strip())
                        plist.append(p0.split()[-1] if p0.split() else p0)
                emit(f"function {fname}({', '.join(plist)}) {{")
                depth += 1
                continue

        m_if = re.match(r"^if\s*\((.*)\)\s*$", s, re.S)
        if m_if:
            emit(f"if ({map_ops_c_to_js(m_if.group(1))}) {{")
            depth += 1
            continue
        m_while = re.match(r"^while\s*\((.*)\)\s*$", s, re.S)
        if m_while:
            emit(f"while ({map_ops_c_to_js(m_while.group(1))}) {{")
            depth += 1
            continue
        if re.match(r"^do\s*$", s):
            emit("do {")
            depth += 1
            continue
        m_dowhile = re.match(r"^}\s*while\s*\((.*)\)\s*;?$", s)
        if m_dowhile:
            depth = max(0, depth - 1)
            emit(f"}} while ({map_ops_c_to_js(m_dowhile.group(1))});")
            continue
        m_switch = re.match(r"^switch\s*\((.*)\)\s*$", s, re.S)
        if m_switch:
            emit(f"switch ({m_switch.group(1)}) {{")
            depth += 1
            continue
        if re.match(r"^case\s+.+?:\s*$", s) or re.match(r"^default\s*:\s*$", s):
            emit(s)
            continue

        m_for = re.match(r"^for\s*\((.*)\)\s*$", s, re.S)
        if m_for:
            parts = split_cond(m_for.group(1))
            if len(parts) == 3:
                init, cond, incr = parts
                init2 = re.sub(
                    r"^(?:(?:const|static|volatile|register|unsigned|signed|long|short|"
                    r"int|char|float|double|bool|auto|size_t)\s+)*([A-Za-z_]\w*)\s*=",
                    r"let \1 =",
                    init,
                )
                emit(f"for ({init2}; {cond}; {incr}) {{")
                depth += 1
                continue
            emit(f"for ({m_for.group(1)}) {{")
            depth += 1
            continue

        # 单行 for：for (i=0;i<n;i++) stmt;
        m_for1 = re.match(r"^for\s*\((.*)\)\s+(.+)$", s)
        if m_for1:
            parts = split_cond(m_for1.group(1))
            if len(parts) == 3:
                init, cond, incr = parts
                init2 = re.sub(
                    r"^(?:(?:const|static|volatile|register|unsigned|signed|long|short|"
                    r"int|char|float|double|bool|auto|size_t)\s+)*([A-Za-z_]\w*)\s*=",
                    r"let \1 =",
                    init,
                )
                emit(f"for ({init2}; {cond}; {incr}) {{ {map_ops_c_to_js(m_for1.group(2).rstrip(';'))}; }}")
                continue
            emit(f"for ({m_for1.group(1)}) {{ {map_ops_c_to_js(m_for1.group(2).rstrip(';'))}; }}")
            continue

        m_pf = re.match(r"^printf\s*\((.*)\)\s*$", s, re.S)
        if m_pf:
            args = split_top(m_pf.group(1))
            if args and args[0].startswith('"'):
                emit(fmt_to_js(args[0][1:-1], args[1:]))
            else:
                emit("// printf 参数异常")
            continue
        m_puts = re.match(r"^puts\s*\((.*)\)\s*$", s, re.S)
        if m_puts:
            arg = m_puts.group(1).strip()
            if arg.startswith('"'):
                emit(f'console.log("{arg[1:-1]}");')
            else:
                emit(f"console.log({arg});")
            continue
        m_sf = re.match(r"^scanf\s*\((.*)\)\s*$", s, re.S)
        if m_sf:
            args = split_top(m_sf.group(1))
            if args and args[0].startswith('"'):
                fmt = args[0][1:-1]
                specs = [p for p in split_format(fmt) if p[0] == "spec"]
                targets = [a.strip().lstrip("&") for a in args[1:]]
                needs_input = True
                for spec, var in zip(specs, targets):
                    typ = spec[2]
                    if typ == "d":
                        emit(f"{var} = _inInt();")
                    elif typ in ("f", "lf"):
                        emit(f"{var} = _inFloat();")
                    else:
                        emit(f"{var} = _in();")
            else:
                emit("// scanf 参数异常")
            continue

        m_cout = re.match(r"^(?:std::)?cout\s*(.*)$", s)
        if m_cout:
            parts = [p.strip() for p in split_multi(m_cout.group(1), "<<") if p.strip()]
            has_end = parts and parts[-1] in ("endl", "std::endl")
            if has_end:
                parts = parts[:-1]
            js_parts = []
            for p in parts:
                if p.startswith('"'):
                    js_parts.append(f'"{p[1:-1]}"')
                else:
                    js_parts.append(map_ops_c_to_js(p))
            if js_parts:
                emit("console.log(" + ", ".join(js_parts) + ");")
            continue
        m_cin = re.match(r"^(?:std::)?cin\s*(.*)$", s)
        if m_cin:
            targets = [p.strip() for p in split_multi(m_cin.group(1), ">>") if p.strip()]
            needs_input = True
            for p in targets:
                emit(f"{p} = _inInt();")
            continue

        m_ret = re.match(r"^return\s*(.*)$", s)
        if m_ret:
            if m_ret.group(1).strip() in ("", "0"):
                emit("return 0;")
            else:
                emit("return " + map_ops_c_to_js(m_ret.group(1)) + ";")
            continue
        if s in ("break", "continue"):
            emit(s + ";")
            continue

        # 声明
        decls = parse_c_decls(s)
        if decls:
            for d in decls:
                name, arr, init = d["name"], d["arr"], d["init"]
                typ = c_type_of(d)
                if arr and not init:
                    n = arr[1:-1]
                    if n == "":
                        emit(f"let {name} = [];")
                    else:
                        emit(f"let {name} = new Array({n}).fill(0);")
                    continue
                if arr and init:
                    ci = c_array_init(init)
                    if ci:
                        emit(f"let {name} = {ci};")
                    else:
                        emit(f"let {name} = {map_ops_c_to_js(init)};")
                    continue
                if init is None:
                    if typ == "str":
                        emit(f"let {name} = '';")
                    elif typ == "bool":
                        emit(f"let {name} = false;")
                    elif typ == "list":
                        emit(f"let {name} = [];")
                    elif typ == "char":
                        emit(f"let {name} = '';")
                    else:
                        emit(f"let {name} = 0;")
                else:
                    i2 = map_ops_c_to_js(init)
                    if re.search(r"\bgetchar\s*\(\s*\)", i2):
                        i2 = re.sub(r"\bgetchar\s*\(\s*\)", "_in()[0]", i2)
                        needs_input = True
                    emit(f"let {name} = {i2};")
            continue

        s2 = s
        if is_cpp:
            s2 = re.sub(r"\.push_back\s*\((.+)\)", r".push(\1)", s2)
            s2 = re.sub(r"\.size\s*\(\s*\)", ".length", s2)
            s2 = re.sub(r"\.length\s*\(\s*\)", ".length", s2)
            s2 = re.sub(r"\.substr\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)", r".substring(\1, \1+\2)", s2)
            m_sort = re.match(
                r"^sort\s*\(([^,]+)\.begin\s*\(\s*\)\s*,\s*\1\.end\s*\(\s*\)\s*\)\s*$", s2
            )
            if m_sort:
                emit(f"{m_sort.group(1)}.sort((a, b) => a - b);")
                continue
        if has_math:
            s2 = re.sub(r"\bsqrt\s*\(", "Math.sqrt(", s2)
            s2 = re.sub(r"\bpow\s*\(", "Math.pow(", s2)
            s2 = re.sub(r"\bfabs\s*\(", "Math.abs(", s2)
            s2 = re.sub(r"\babs\s*\(", "Math.abs(", s2)
        s2 = re.sub(r"\bstrlen\s*\(([^)]*)\)", r"\1.length", s2)
        s2 = re.sub(r"\bstrcmp\s*\(([^,)]+)\s*,\s*([^)]+)\)", r"(\1 === \2)", s2)
        s2 = re.sub(r"\bstrcpy\s*\(([^,)]+)\s*,\s*([^)]+)\)", r"\1 = \2", s2)
        s2 = re.sub(r"\bstrcat\s*\(([^,)]+)\s*,\s*([^)]+)\)", r"\1 += \2", s2)
        if not s2.endswith(";"):
            s2 += ";"
        emit(map_ops_c_to_js(s2))

    if saw_main:
        out.append("")
        out.append("main();")

    if needs_input:
        helper = (
            "const fs = require('fs');\n"
            "function _readLine() {\n"
            "  const buf = Buffer.alloc(1);\n"
            "  let s = '';\n"
            "  while (true) {\n"
            "    const n = fs.readSync(0, buf, 0, 1, null);\n"
            "    if (n === 0 || buf[0] === 10) break;\n"
            "    s += String.fromCharCode(buf[0]);\n"
            "  }\n"
            "  return s.replace(/\\r$/, '');\n"
            "}\n"
            "function _in() { return _readLine(); }\n"
            "function _inInt() { return parseInt(_readLine(), 10); }\n"
            "function _inFloat() { return parseFloat(_readLine()); }\n"
        )
        out = [helper, ""] + out
    return join_lines(out)


# ---------------------------------------------------------------------------
# Python -> C / C++
# ---------------------------------------------------------------------------

def py_to_clike(code, is_cpp=False):
    lines = code.splitlines()
    func_lines, main_lines = [], []
    fdepth, mdepth = 0, 0
    stream = "main"  # main | func
    sym = SymTable()
    imports = []
    saw_def = False
    saw_def_main = False
    guard_base = None  # 正在收集 __main__ 守卫体（记录守卫行的缩进深度）
    guard_collect = []
    saw_guard = False
    sum_counter = 0

    def expand_sum_range(expr, tmp_var):
        """sum(range(a,b[,step])) -> C 循环累加行列表；非该模式返回 None"""
        m = re.match(r"^\s*sum\(\s*range\(\s*([^()]*?)\s*\)\s*\)\s*$", expr)
        if not m:
            return None
        parts = [p.strip() for p in split_top(m.group(1), ",") if p.strip()]
        if len(parts) == 1:
            start, end, step = "0", parts[0], "1"
        elif len(parts) == 2:
            start, end, step = parts[0], parts[1], "1"
        elif len(parts) == 3:
            start, end, step = parts[0], parts[1], parts[2]
        else:
            return None
        ivar = "__i"
        rows = [f"int {tmp_var} = 0;"]
        if step.startswith("-"):
            rows.append(f"for (int {ivar} = {map_ops_py_to_c(start)}; {ivar} > {map_ops_py_to_c(end)}; {ivar} += {map_ops_py_to_c(step)}) {{")
        else:
            rows.append(f"for (int {ivar} = {map_ops_py_to_c(start)}; {ivar} < {map_ops_py_to_c(end)}; {ivar} += {map_ops_py_to_c(step)}) {{")
        rows.append(f"    {tmp_var} += {ivar};")
        rows.append("}")
        return rows

    def emit(line):
        target = func_lines if stream == "func" else main_lines
        target.append(" " * (4 * (fdepth if stream == "func" else mdepth)) + line)

    def close_to(new_depth):
        nonlocal fdepth, mdepth
        if stream == "func":
            while fdepth > new_depth:
                fdepth -= 1
                func_lines.append(" " * (4 * fdepth) + "}")
        else:
            while mdepth > new_depth:
                mdepth -= 1
                main_lines.append(" " * (4 * mdepth) + "}")

    for raw in lines:
        if not raw.strip():
            (func_lines if stream == "func" else main_lines).append("")
            continue
        indent = len(raw) - len(raw.lstrip())
        new_depth = indent // 4
        line, comment = strip_comment(raw, "python")
        s = line.strip()
        if not s:
            if comment:
                emit("// " + comment)
            continue

        # __main__ 守卫
        if guard_base is not None:
            if new_depth <= guard_base:
                body = guard_collect
                guard_collect = []
                guard_base = None
                if not (saw_def and len(body) == 1 and body[0].strip() == "main()"):
                    main_lines.append("// if __name__ == '__main__' 守卫：已并入程序入口")
                    for b in body:
                        main_lines.append("    " + b if not b.strip() else b)
                # 继续处理当前行
            else:
                off = 4 * (guard_base + 1)
                guard_collect.append(raw[off:] if len(raw) >= off else "")
                continue
        m_guard = re.match(r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:\s*$", s)
        if m_guard:
            saw_guard = True
            guard_base = new_depth
            guard_collect = []
            continue

        if s.startswith("import ") or s.startswith("from "):
            if re.search(r"\bmath\b", s):
                imports.append("#include <math.h>")
            elif re.search(r"\brandom\b", s):
                imports.append("#include <stdlib.h>  // rand/srand 需人工适配")
            else:
                imports.append(f"// import 语句需人工适配: {s}")
            continue
        if s.startswith("class "):
            emit("// class 定义需人工适配为 C 结构体/函数")
            continue

        # def
        m_def = re.match(r"^def\s+([A-Za-z_]\w*)\s*\((.*)\)\s*:\s*$", s)
        if m_def:
            fname, params = m_def.group(1), m_def.group(2)
            if stream == "func":
                close_to(0)
            # 关闭顶层未闭合块
            close_to(0)
            stream = "func"
            fdepth = 0
            plist = []
            for p in split_top(params):
                pname = re.sub(r"\s*=.*", "", p).strip()
                if pname and pname != "self":
                    sym.declare(pname, "int")
                    plist.append(f"int {pname}")
            if fname == "main":
                emit("int main() {")
                saw_def_main = True
            else:
                emit(f"int {fname}({', '.join(plist)}) {{  // 参数类型为推断，请人工核对")
            fdepth = 1
            saw_def = True
            continue

        # elif / else：先静默收口再合并输出
        m_elif = re.match(r"^elif\s+(.+?)\s*:\s*(.*)$", s)
        if m_elif:
            if stream == "func":
                while fdepth > max(0, new_depth):
                    fdepth -= 1
                emit(f"}} else if ({map_ops_py_to_c(m_elif.group(1))}) {{")
                if not m_elif.group(2).strip():
                    fdepth += 1
            else:
                while mdepth > max(0, new_depth):
                    mdepth -= 1
                emit(f"}} else if ({map_ops_py_to_c(m_elif.group(1))}) {{")
                if not m_elif.group(2).strip():
                    mdepth += 1
            continue
        m_else = re.match(r"^else\s*:\s*(.*)$", s)
        if m_else:
            tail = m_else.group(1).strip()
            if stream == "func":
                while fdepth > max(0, new_depth):
                    fdepth -= 1
                if tail:
                    emit(f"}} else {{ {map_ops_py_to_c(tail.rstrip())}; }}")
                else:
                    emit("} else {")
                    fdepth += 1
            else:
                while mdepth > max(0, new_depth):
                    mdepth -= 1
                if tail:
                    emit(f"}} else {{ {map_ops_py_to_c(tail.rstrip())}; }}")
                else:
                    emit("} else {")
                    mdepth += 1
            continue

        # 缩进减小 -> 闭合
        if stream == "func":
            if new_depth <= 0:
                close_to(0)
                stream = "main"
                mdepth = 0
            elif new_depth < fdepth:
                close_to(new_depth)
        else:
            if new_depth < mdepth:
                close_to(new_depth)

        m_if = re.match(r"^if\s+(.+?)\s*:\s*(.*)$", s)
        if m_if:
            cond = map_ops_py_to_c(m_if.group(1))
            tail = m_if.group(2).strip()
            if tail:
                emit(f"if ({cond}) {{ {map_ops_py_to_c(tail.rstrip())}; }}")
            else:
                emit(f"if ({cond}) {{")
                if stream == "func":
                    fdepth += 1
                else:
                    mdepth += 1
            continue
        m_while = re.match(r"^while\s+(.+?)\s*:\s*(.*)$", s)
        if m_while:
            cond = map_ops_py_to_c(m_while.group(1))
            tail = m_while.group(2).strip()
            if tail:
                emit(f"while ({cond}) {{ {map_ops_py_to_c(tail.rstrip())}; }}")
            else:
                emit(f"while ({cond}) {{")
                if stream == "func":
                    fdepth += 1
                else:
                    mdepth += 1
            continue
        m_for = re.match(r"^for\s+(.+?)\s+in\s+range\s*\((.*)\)\s*:\s*(.*)$", s)
        if m_for:
            var = m_for.group(1).strip()
            rargs = [a.strip() for a in split_top(m_for.group(2))]
            if len(rargs) == 1:
                emit(f"for (int {var} = 0; {var} < {map_ops_py_to_c(rargs[0])}; {var}++) {{")
            elif len(rargs) == 2:
                emit(f"for (int {var} = {map_ops_py_to_c(rargs[0])}; {var} < {map_ops_py_to_c(rargs[1])}; {var}++) {{")
            else:
                a, b, st = (map_ops_py_to_c(rargs[0]), map_ops_py_to_c(rargs[1]), map_ops_py_to_c(rargs[2]))
                if st == "-1":
                    emit(f"for (int {var} = {a}; {var} > {b}; {var}--) {{")
                elif st.startswith("-"):
                    emit(f"for (int {var} = {a}; {var} > {b}; {var} {st}) {{")
                else:
                    emit(f"for (int {var} = {a}; {var} < {b}; {var} += {st}) {{")
            if stream == "func":
                fdepth += 1
            else:
                mdepth += 1
            continue
        m_for2 = re.match(r"^for\s+(.+?)\s+in\s+(.+?)\s*:\s*(.*)$", s)
        if m_for2:
            var, coll = m_for2.group(1).strip(), m_for2.group(2).strip()
            emit(f"// for {var} in {coll}: 请人工改为下标循环")
            emit(f"for (int {var} = 0; {var} < {coll}.length; {var}++) {{")
            if stream == "func":
                fdepth += 1
            else:
                mdepth += 1
            continue

        # 输入
        m_input = re.match(r"^([A-Za-z_]\w*)\s*=\s*(int|float|str)?\s*\(\s*input\s*\(\s*\)\s*\)\s*$", s)
        if m_input:
            var, cast = m_input.group(1), m_input.group(2) or "str"
            if cast == "int":
                emit(f"int {var};")
                emit(f'scanf("%d", &{var});')
                sym.declare(var, "int")
            elif cast == "float":
                emit(f"float {var};")
                emit(f'scanf("%f", &{var});')
                sym.declare(var, "float")
            else:
                emit(f"char {var}[256];")
                emit(f'scanf("%s", {var});  // 输入类型按字符串处理')
                sym.declare(var, "str")
            continue

        # 赋值
        m_assign = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", s)
        if m_assign:
            var, rhs = m_assign.group(1), m_assign.group(2).strip()
            sr = expand_sum_range(rhs, var)
            if sr:
                for l in sr:
                    emit(l)
                sym.declare(var, "int")
                continue
            m_list = re.match(r"^\[\s*0\s*\]\s*\*\s*(.+)$", rhs)
            if m_list:
                n = map_ops_py_to_c(m_list.group(1))
                emit(f"int {var}[{n}];  // 变长数组，需 C99")
                sym.declare(var, "list")
                continue
            m_list2 = re.match(r"^\[(.*)\]$", rhs)
            if m_list2:
                inner = m_list2.group(1).strip()
                if inner:
                    emit(f"int {var}[] = {{{inner}}};")
                else:
                    emit(f"int {var}[10];  // 空列表，长度请人工指定")
                sym.declare(var, "list")
                continue
            t = guess_type(rhs)
            if t == "int":
                emit(f"int {var} = {map_ops_py_to_c(rhs)};")
            elif t == "float":
                emit(f"float {var} = {map_ops_py_to_c(rhs)};")
            elif t == "str":
                if rhs.startswith('"') or rhs.startswith("'"):
                    lit = rhs[1:-1].replace('"', '\\"')
                    emit(f'char {var}[] = "{lit}";')
                else:
                    emit(f"char {var}[256];  // 字符串赋值需人工处理: {rhs}")
            elif t == "bool":
                emit(f"bool {var} = {map_ops_py_to_c(rhs)};")
            else:
                if var in sym.vars:
                    if sym.vars[var] == "str":
                        emit(f"strcpy({var}, {rhs});")
                    elif sym.vars[var] == "float":
                        emit(f"{var} = {map_ops_py_to_c(rhs)};")
                    else:
                        emit(f"{var} = {map_ops_py_to_c(rhs)};")
                else:
                    emit(f"int {var} = {map_ops_py_to_c(rhs)};  // 类型为推断")
                    sym.declare(var, "int", rhs)
            continue

        m_print = re.match(r"^print\s*\((.*)\)\s*$", s, re.S)
        if m_print:
            args = split_top(m_print.group(1))
            if args and args[-1].startswith("end="):
                args = args[:-1]
            new_args = []
            for a in args:
                a = a.strip()
                if not (a.startswith('"') or a.startswith("'")):
                    mm = re.search(r"sum\(\s*range\([^()]*\)\s*\)", a)
                    if mm:
                        tmp = f"_sum{sum_counter}"
                        sum_counter += 1
                        for l in expand_sum_range(mm.group(0), tmp):
                            emit(l)
                        sym.declare(tmp, "int")
                        a = a.replace(mm.group(0), tmp)
                new_args.append(a)
            for st in py_print_to_c(new_args, sym):
                emit(st)
            continue

        m_ret = re.match(r"^return\s+(.+)$", s)
        if m_ret:
            emit("return " + map_ops_py_to_c(m_ret.group(1)) + ";")
            continue
        if s == "return":
            emit("return 0;")
            continue
        if s in ("break", "continue"):
            emit(s + ";")
            continue

        s2 = map_ops_py_to_c(s)
        s2 = re.sub(r"\.append\s*\((.+)\)", r"// .append(\1) 请人工改为数组操作", s2)
        s2 = re.sub(r"\.split\s*\(.*\)", "// .split() 请人工处理", s2)
        s2 = re.sub(r"\.join\s*\(.*\)", "// .join() 请人工处理", s2)
        s2 = re.sub(r"\.strip\s*\(\s*\)", "", s2)
        s2 = re.sub(r"len\s*\(([^)]*)\)", r"strlen(\1)  // len() 请人工核对", s2)
        if not s2.endswith(";"):
            s2 += ";"
        emit(s2)

    # 收尾
    if guard_base is not None:
        body = guard_collect
        if not (saw_def and len(body) == 1 and body[0].strip() == "main()"):
            main_lines.append("// if __name__ == '__main__' 守卫：已并入程序入口")
            for b in body:
                main_lines.append(b if not b.strip() else b)
    close_to(0)
    if stream == "func":
        stream = "main"

    body = "\n".join(main_lines).strip("\n")
    funcs = "\n".join(func_lines).strip("\n")
    parts = []
    if imports:
        parts.extend(imports)
        parts.append("")
    if funcs:
        parts.append(funcs)
    if body or not saw_def:
        if saw_def_main:
            parts.append("// 顶层语句在 C 中需移入 main()，请人工调整")
            for ln in body.splitlines():
                parts.append("    " + ln if ln.strip() else "")
        else:
            if body and saw_def:
                parts.append("// 顶层语句已并入 main()")
            parts.append("int main() {")
            for ln in body.splitlines():
                parts.append("    " + ln if ln.strip() else "")
            parts.append("    return 0;")
            parts.append("}")
    result = "\n".join(parts)
    result = join_lines(result.splitlines())
    # 自动补充必要的 C 头文件
    headers = []
    if re.search(r"\b(?:printf|scanf)\s*\(", result):
        headers.append("#include <stdio.h>")
    if re.search(r"\b(?:strcpy|strlen|strcat|strcmp|memset|memcpy)\s*\(", result):
        headers.append("#include <string.h>")
    if re.search(r"\b(?:sqrt|pow|fabs|sin|cos|tan|log|exp)\s*\(", result):
        headers.append("#include <math.h>")
    if re.search(r"\b(?:rand|srand)\s*\(", result):
        headers.append("#include <stdlib.h>")
    if headers:
        extra = "\n".join(headers) + "\n"
        if result.startswith("#include") or result.startswith("//"):
            result = result.replace("\n", "\n", 1)  # no-op safety
            lines = result.splitlines(True)
            insert_at = 0
            while insert_at < len(lines) and lines[insert_at].startswith(("#", "//")):
                insert_at += 1
            lines.insert(insert_at, "\n".join(headers) + "\n")
            result = "".join(lines)
        else:
            result = extra + result
    return result


def py_print_to_c(args, sym):
    if not args:
        return ["printf(\"\\n\");"]
    fmt = ""
    cargs = []
    for a in args:
        a = a.strip()
        if a.startswith('"') or a.startswith("'"):
            fmt += a[1:-1].replace('"', '\\"').replace("%", "%%")
        else:
            t = sym.get(a)
            if t == "str":
                fmt += "%s"
            elif t == "float":
                fmt += "%f"
            elif t == "bool":
                fmt += "%d"
            else:
                fmt += "%d"
            cargs.append(a)
    fmt += "\\n"
    if cargs:
        return [f'printf("{fmt}", {", ".join(cargs)});']
    return [f'printf("{fmt}");']


# ---------------------------------------------------------------------------
# Python -> JavaScript
# ---------------------------------------------------------------------------

def py_to_js(code):
    lines = code.splitlines()
    out = []
    depth = 0
    needs_input = False

    def emit(s):
        out.append("  " * depth + s)

    for raw in lines:
        if not raw.strip():
            out.append("")
            continue
        indent = len(raw) - len(raw.lstrip())
        new_depth = indent // 4
        line, comment = strip_comment(raw, "python")
        s = line.strip()
        if not s:
            if comment:
                emit("// " + comment)
            continue

        if s.startswith("import ") or s.startswith("from "):
            emit("// import: " + s)
            continue
        if s.startswith("class "):
            emit("// class " + s[len("class "):] + " 需人工适配为 JS class")
            continue

        m_def = re.match(r"^def\s+([A-Za-z_]\w*)\s*\((.*)\)\s*:\s*$", s)
        if m_def:
            while depth > 0:
                depth -= 1
                emit("}")
            params = [p.split("=")[0].strip() for p in split_top(m_def.group(2)) if p.strip() and p.strip() != "self"]
            emit(f"function {m_def.group(1)}({', '.join(params)}) {{")
            depth = 1
            continue

        # elif / else：先静默收口再合并输出
        m_elif = re.match(r"^elif\s+(.+?)\s*:\s*(.*)$", s)
        if m_elif:
            while depth > max(0, new_depth):
                depth -= 1
            tail = m_elif.group(2).strip()
            if tail:
                emit(f"}} else if ({map_ops_py_to_js(m_elif.group(1))}) {{ {map_ops_py_to_js(tail.rstrip())}; }}")
            else:
                emit(f"}} else if ({map_ops_py_to_js(m_elif.group(1))}) {{")
                depth += 1
            continue
        m_else = re.match(r"^else\s*:\s*(.*)$", s)
        if m_else:
            while depth > max(0, new_depth):
                depth -= 1
            tail = m_else.group(1).strip()
            if tail:
                emit(f"}} else {{ {map_ops_py_to_js(tail.rstrip())}; }}")
            else:
                emit("} else {")
                depth += 1
            continue

        if new_depth < depth:
            while depth > new_depth:
                depth -= 1
                emit("}")

        m_if = re.match(r"^if\s+(.+?)\s*:\s*(.*)$", s)
        if m_if:
            tail = m_if.group(2).strip()
            if tail:
                emit(f"if ({map_ops_py_to_js(m_if.group(1))}) {{ {map_ops_py_to_js(tail.rstrip())}; }}")
            else:
                emit(f"if ({map_ops_py_to_js(m_if.group(1))}) {{")
                depth += 1
            continue
        m_while = re.match(r"^while\s+(.+?)\s*:\s*(.*)$", s)
        if m_while:
            tail = m_while.group(2).strip()
            if tail:
                emit(f"while ({map_ops_py_to_js(m_while.group(1))}) {{ {map_ops_py_to_js(tail.rstrip())}; }}")
            else:
                emit(f"while ({map_ops_py_to_js(m_while.group(1))}) {{")
                depth += 1
            continue
        m_for = re.match(r"^for\s+(.+?)\s+in\s+range\s*\((.*)\)\s*:\s*(.*)$", s)
        if m_for:
            var = m_for.group(1).strip()
            rargs = [a.strip() for a in split_top(m_for.group(2))]
            tail = m_for.group(3).strip()
            if len(rargs) == 1:
                inner = f"for (let {var} = 0; {var} < {rargs[0]}; {var}++)"
            elif len(rargs) == 2:
                inner = f"for (let {var} = {rargs[0]}; {var} < {rargs[1]}; {var}++)"
            else:
                inner = f"for (let {var} = {rargs[0]}; {var} < {rargs[1]}; {var} += {rargs[2]})"
            if tail:
                emit(inner + " { " + map_ops_py_to_js(tail.rstrip()) + "; }")
            else:
                emit(inner + " {")
                depth += 1
            continue
        m_for2 = re.match(r"^for\s+(.+?)\s+in\s+(.+?)\s*:\s*(.*)$", s)
        if m_for2:
            emit(f"for (const {m_for2.group(1).strip()} of {m_for2.group(2).strip()}) {{")
            depth += 1
            continue

        m_print = re.match(r"^print\s*\((.*)\)\s*$", s, re.S)
        if m_print:
            args = split_top(m_print.group(1))
            kw_end = None
            if args and args[-1].startswith("end="):
                kw_end = args[-1]
                args = args[:-1]
            js_args = []
            for a in args:
                a = a.strip()
                if a.startswith("f") and a[1:2] in "\"'" and a.endswith(a[1]):
                    inner = a[2:-1]
                    inner = re.sub(r"\{([^}]+)\}", r"${ \1 }", inner)
                    js_args.append("`" + inner + "`")
                    continue
                js_args.append(map_ops_py_to_js(a))
            if kw_end:
                end_val = kw_end.split("=", 1)[1].strip()
                if end_val in ('""', "''") and js_args:
                    emit("process.stdout.write(String(" + js_args[0] + "));")
                    continue
            emit("console.log(" + ", ".join(js_args) + ");")
            continue

        m_input = re.match(r"^([A-Za-z_]\w*)\s*=\s*(int|float|str)?\s*\(\s*input\s*\(\s*\)\s*\)\s*$", s)
        if m_input:
            var, cast = m_input.group(1), m_input.group(2) or "str"
            needs_input = True
            if cast == "int":
                emit(f"let {var} = _inInt();")
            elif cast == "float":
                emit(f"let {var} = _inFloat();")
            else:
                emit(f"let {var} = _in();")
            continue

        m_ret = re.match(r"^return\s+(.+)$", s)
        if m_ret:
            emit("return " + map_ops_py_to_js(m_ret.group(1)) + ";")
            continue
        if s == "return":
            emit("return;")
            continue
        if s in ("break", "continue"):
            emit(s + ";")
            continue

        m_assign = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", s)
        if m_assign:
            var, rhs = m_assign.group(1), m_assign.group(2).strip()
            m_list = re.match(r"^\[(.*)\]\s*\*\s*(.+)$", rhs)
            if m_list:
                fill = m_list.group(1).strip() or "0"
                emit(f"let {var} = new Array({m_list.group(2)}).fill({fill});")
                continue
            if rhs.startswith("["):
                emit(f"let {var} = {rhs};")
                continue
            t = guess_type(rhs)
            if t is None:
                emit(f"{var} = {map_ops_py_to_js(rhs)};")
            else:
                emit(f"let {var} = {map_ops_py_to_js(rhs)};")
            continue

        s2 = map_ops_py_to_js(s)
        s2 = re.sub(r"\.append\s*\((.+)\)", r".push(\1)", s2)
        s2 = re.sub(r"len\s*\(([^)]*)\)", r"\1.length", s2)
        if not s2.endswith(";"):
            s2 += ";"
        emit(s2)

    while depth > 0:
        depth -= 1
        emit("}")

    result = "\n".join(out)
    if needs_input:
        helper = (
            "const fs = require('fs');\n"
            "function _readLine() {\n"
            "  const buf = Buffer.alloc(1);\n"
            "  let s = '';\n"
            "  while (true) {\n"
            "    const n = fs.readSync(0, buf, 0, 1, null);\n"
            "    if (n === 0 || buf[0] === 10) break;\n"
            "    s += String.fromCharCode(buf[0]);\n"
            "  }\n"
            "  return s.replace(/\\r$/, '');\n"
            "}\n"
            "function _in() { return _readLine(); }\n"
            "function _inInt() { return parseInt(_readLine(), 10); }\n"
            "function _inFloat() { return parseFloat(_readLine()); }\n"
        )
        result = helper + "\n\n" + result
    return join_lines(result.splitlines())


# ---------------------------------------------------------------------------
# JavaScript -> Python / C（基础版）
# ---------------------------------------------------------------------------

def js_to_python(code):
    lines = code.splitlines()
    out = []
    depth = 0
    sym = SymTable()
    skip_braces = None

    def emit(s):
        out.append(" " * (4 * depth) + s)

    for raw in lines:
        if not raw.strip():
            out.append("")
            continue
        line, comment = strip_comment(raw, "javascript")
        s = line.strip()
        if not s:
            if comment:
                emit("# " + comment)
            continue
        # 跳过输入辅助函数
        if skip_braces is not None:
            skip_braces += s.count("{") - s.count("}")
            if skip_braces <= 0:
                skip_braces = None
            continue
        if s.startswith(("const fs = require", "function _readLine", "function _inInt", "function _inFloat", "function _in(")):
            skip_braces = s.count("{") - s.count("}")
            if skip_braces <= 0:
                skip_braces = None
            continue

        m_else = re.match(r"^\}\s*else\s*(if\s*\((.*)\))?\s*$", s, re.S)
        if m_else:
            depth = max(0, depth - 1)
            if m_else.group(2) is not None:
                emit(f"elif {map_ops_js_to_py(m_else.group(2))}:")
            else:
                emit("else:")
            depth += 1
            continue
        if s == "}":
            depth = max(0, depth - 1)
            continue
        if s.endswith("{"):
            s = s[:-1].rstrip()

        m_func = re.match(r"^function\s+([A-Za-z_]\w*)\s*\((.*)\)\s*$", s)
        if m_func:
            params = [p.strip() for p in split_top(m_func.group(2)) if p.strip()]
            emit(f"def {m_func.group(1)}({', '.join(params)}):")
            depth += 1
            continue

        m_if = re.match(r"^if\s*\((.*)\)\s*$", s, re.S)
        if m_if:
            emit(f"if {map_ops_js_to_py(m_if.group(1))}:")
            depth += 1
            continue
        m_while = re.match(r"^while\s*\((.*)\)\s*$", s, re.S)
        if m_while:
            emit(f"while {map_ops_js_to_py(m_while.group(1))}:")
            depth += 1
            continue
        m_for = re.match(r"^for\s*\((.*)\)\s*$", s, re.S)
        if m_for:
            parts = split_cond(m_for.group(1))
            if len(parts) == 3:
                r = js_for_to_range(parts[0], parts[1], parts[2])
                if r:
                    emit(f"for {r}:")
                    depth += 1
                    continue
            emit("# for 循环未能自动转换，请人工处理")
            depth += 1
            continue

        m_log = re.match(r"^console\.log\s*\((.*)\)\s*;?\s*$", s, re.S)
        if m_log:
            inner = m_log.group(1).strip()
            if inner.startswith("`") and inner.endswith("`"):
                lit = inner[1:-1]
                lit = re.sub(r"\$\{\s*([^}]+?)\s*\}", r"{\1}", lit)
                emit(f'print(f"{lit}")')
                continue
            args = [js_concat_to_py_fstring(a) for a in split_top(inner) if a.strip()]
            emit(f"print({', '.join(args)})")
            continue

        m_ret = re.match(r"^return\s*(.*);?$", s)
        if m_ret:
            emit("return " + map_ops_js_to_py(m_ret.group(1)) if m_ret.group(1).strip() else "return")
            continue
        if s in ("break;", "continue;"):
            emit(s[:-1])
            continue

        m_assign = re.match(r"^(?:let|var|const)\s+([A-Za-z_]\w*)\s*=\s*(.+?);?$", s)
        if m_assign:
            var, rhs = m_assign.group(1), m_assign.group(2).strip()
            m_arr = re.match(r"^new Array\((.+)\)\.fill\((.+)\)$", rhs)
            if m_arr:
                emit(f"{var} = [{m_arr.group(2)}] * {m_arr.group(1)}")
                sym.declare(var, "list")
                continue
            if rhs.startswith("["):
                emit(f"{var} = {rhs}")
                sym.declare(var, "list")
                continue
            if rhs == "_inInt()":
                emit(f"{var} = int(input())")
                sym.declare(var, "int")
                continue
            if rhs == "_inFloat()":
                emit(f"{var} = float(input())")
                sym.declare(var, "float")
                continue
            if rhs == "_in()":
                emit(f"{var} = input()")
                sym.declare(var, "str")
                continue
            emit(f"{var} = {js_concat_to_py_fstring(rhs)}")
            sym.declare(var, guess_type(rhs) or "int")
            continue
        m_assign2 = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+?);?$", s)
        if m_assign2:
            var, rhs = m_assign2.group(1), m_assign2.group(2).strip()
            if rhs == "_inInt()":
                emit(f"{var} = int(input())")
            elif rhs == "_inFloat()":
                emit(f"{var} = float(input())")
            elif rhs == "_in()":
                emit(f"{var} = input()")
            else:
                emit(f"{var} = {js_concat_to_py_fstring(rhs)}")
            continue

        s2 = map_ops_js_to_py(s.rstrip(";"))
        s2 = re.sub(r"\.push\s*\((.+)\)", r".append(\1)", s2)
        s2 = re.sub(r"\.length\b", ".__len__()", s2)
        emit(s2)

    return join_lines(out)


def js_for_to_range(init, cond, incr):
    m = re.match(r"(?:let|var|const)?\s*([A-Za-z_]\w*)\s*=\s*(.+)", init)
    if not m:
        return None
    var, start = m.group(1), m.group(2)
    m2 = re.match(rf"^\s*{re.escape(var)}\s*(<=|<|>=|>)\s*(.+?)\s*$", cond)
    if not m2:
        return None
    op, bound = m2.group(1), m2.group(2)
    m3 = re.match(rf"^\s*{re.escape(var)}\s*(\+\+|--|\+=|-=)\s*(\d*)\s*$", incr)
    if not m3:
        return None
    op2, k = m3.group(1), m3.group(2) or "1"
    if op2 in ("++", "--"):
        step = "1" if op2 == "++" else "-1"
    else:
        step = k if op2 == "+=" else f"-{k}"
    if step == "1":
        if op == "<":
            return f"{var} in range({start}, {bound})"
        if op == "<=":
            return f"{var} in range({start}, {bound} + 1)"
        if op == ">":
            return f"{var} in range({start}, {bound}, -1)"
        return f"{var} in range({start}, {bound} - 1, -1)"
    if step.startswith("-"):
        if op == ">":
            return f"{var} in range({start}, {bound}, {step})"
        return f"{var} in range({start}, {bound} - 1, {step})"
    if op == "<":
        return f"{var} in range({start}, {bound}, {step})"
    return f"{var} in range({start}, {bound} + 1, {step})"


def js_to_c(code):
    py = js_to_python(code)
    return py_to_clike(py, is_cpp=False)


# ---------------------------------------------------------------------------
# 调度
# ---------------------------------------------------------------------------

def c_to_cpp(code):
    body = code
    body = body.replace("#include <stdio.h>", "#include <iostream>\n#include <cstdio>")
    body = body.replace("#include <stdlib.h>", "#include <cstdlib>")
    body = body.replace("#include <string.h>", "#include <cstring>")
    body = body.replace("#include <math.h>", "#include <cmath>")
    return "// C -> C++：主要为头文件与类型适配，请人工核对\n" + body


def cpp_to_c(code):
    out = []
    for ln in code.splitlines():
        s = ln.strip()
        if s.startswith("#include <iostream") or s.startswith("using namespace"):
            continue
        if "cout" in s or "cin" in s or "endl" in s:
            out.append(ln + "  // TODO: cout/cin 需人工改为 printf/scanf")
            continue
        out.append(ln)
    return "// C++ -> C：cout/cin、string、vector 等需人工调整\n" + "\n".join(out)


PAIR_FN = {
    ("c", "python"): lambda code: clike_to_python(code, False),
    ("cpp", "python"): lambda code: clike_to_python(code, True),
    ("c", "javascript"): lambda code: clike_to_js(code, False),
    ("cpp", "javascript"): lambda code: clike_to_js(code, True),
    ("c", "cpp"): c_to_cpp,
    ("cpp", "c"): cpp_to_c,
    ("python", "c"): lambda code: py_to_clike(code, False),
    ("python", "cpp"): lambda code: py_to_clike(code, True),
    ("python", "javascript"): lambda code: py_to_js(code),
    ("javascript", "python"): lambda code: js_to_python(code),
    ("javascript", "c"): lambda code: js_to_c(code),
    ("javascript", "cpp"): lambda code: js_to_c(code),
}

LANG_NAMES = {
    "c": "C",
    "cpp": "C++",
    "python": "Python",
    "javascript": "JavaScript",
}

SUPPORTED_PAIRS = set(PAIR_FN.keys())


def convert(source, src_lang, dst_lang):
    """入口：返回 (成功, 结果代码 或 错误信息)"""
    if src_lang == dst_lang:
        return True, source
    key = (src_lang, dst_lang)
    if key not in PAIR_FN:
        return False, f"规则引擎暂不支持 {LANG_NAMES.get(src_lang, src_lang)} -> {LANG_NAMES.get(dst_lang, dst_lang)} 的转换，请使用「AI 转换」。"
    if not source.strip():
        return False, "源代码为空，请先在左侧编写代码。"
    try:
        result = PAIR_FN[key](source)
        if not result.strip():
            return False, "转换结果为空，请检查源代码。"
        return True, result
    except Exception as e:
        return False, f"规则引擎转换失败：{e}\n请使用「AI 转换」或人工处理。"


if __name__ == "__main__":
    pass
