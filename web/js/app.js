/* ===== 代码转换器 · 前端逻辑 ===== */
(function () {
  "use strict";

  var LANGS = [
    { id: "c", name: "C", mode: "text/x-csrc" },
    { id: "cpp", name: "C++", mode: "text/x-c++src" },
    { id: "python", name: "Python", mode: "text/x-python" },
    { id: "javascript", name: "JavaScript", mode: "javascript" },
  ];

  var TEMPLATES = {
    c: [
      "#include <stdio.h>",
      "",
      "int main() {",
      "    int n, sum = 0;",
      "    printf(\"请输入一个整数 n: \");",
      "    scanf(\"%d\", &n);",
      "    for (int i = 1; i <= n; i++) {",
      "        sum += i;",
      "    }",
      "    printf(\"1 到 %d 的和 = %d\\n\", n, sum);",
      "    return 0;",
      "}",
    ].join("\n"),
    cpp: [
      "#include <iostream>",
      "using namespace std;",
      "",
      "int add(int a, int b) {",
      "    return a + b;",
      "}",
      "",
      "int main() {",
      "    int x, y;",
      "    cout << \"请输入两个整数: \";",
      "    cin >> x >> y;",
      "    cout << x << \" + \" << y << \" = \" << add(x, y) << endl;",
      "    return 0;",
      "}",
    ].join("\n"),
    python: [
      'n = int(input("请输入一个整数 n: "))',
      "sum = 0",
      "for i in range(1, n + 1):",
      "    sum += i",
      'print("1 到 %d 的和 = %d" % (n, sum))',
    ].join("\n"),
    javascript: [
      "function sumUp(n) {",
      "    let sum = 0;",
      "    for (let i = 1; i <= n; i++) {",
      "        sum += i;",
      "    }",
      "    return sum;",
      "}",
      "",
      "const n = 5;",
      "console.log(`1 到 ${n} 的和 = ${sumUp(n)}`);",
    ].join("\n"),
  };

  var $ = function (id) { return document.getElementById(id); };

  var srcLang = "c";
  var dstLang = "python";
  var srcEditor, dstEditor;

  // ---------- 初始化语言选择 ----------
  function fillSelects() {
    var s1 = $("srcLang"), s2 = $("dstLang");
    LANGS.forEach(function (l) {
      s1.appendChild(new Option(l.name, l.id));
      s2.appendChild(new Option(l.name, l.id));
    });
    s1.value = srcLang;
    s2.value = dstLang;
    s1.addEventListener("change", function () {
      srcLang = s1.value;
      srcEditor.setOption("mode", langById(srcLang).mode);
      loadSample(false);
    });
    s2.addEventListener("change", function () {
      dstLang = s2.value;
      dstEditor.setOption("mode", langById(dstLang).mode);
    });
  }

  function langById(id) {
    for (var i = 0; i < LANGS.length; i++) if (LANGS[i].id === id) return LANGS[i];
    return LANGS[0];
  }

  // ---------- 输入需求检测（防止 scanf/input 读到空输入跑出垃圾结果） ----------
  function needsInput(code, lang) {
    if (!code) return false;
    if (lang === "c" || lang === "cpp") {
      return /scanf\s*\(|cin\s*>>|getchar\s*\(|gets\s*\(/.test(code);
    }
    if (lang === "python") {
      return /\binput\s*\(/.test(code);
    }
    if (lang === "javascript") {
      return /_inInt\s*\(|_inFloat\s*\(|_in\s*\(|readline|readSync|process\.stdin/.test(code);
    }
    return false;
  }

  function ensureStdin(code, lang, outEl) {
    if (needsInput(code, lang) && !$("stdin").value.trim()) {
      flashOutput(outEl, "程序需要键盘输入：请先在「标准输入」框中填写（每行一个值，示例可填 5）");
      $("stdin").focus();
      return false;
    }
    return true;
  }

  // ---------- CodeMirror ----------
  function makeEditor(host, value, mode) {
    var cm = CodeMirror(host, {
      value: value,
      mode: mode,
      lineNumbers: true,
      lineWrapping: false,
      indentUnit: 4,
      tabSize: 4,
      indentWithTabs: false,
      styleActiveLine: true,
      matchBrackets: true,
      autoCloseBrackets: true,
      extraKeys: { "Ctrl-Enter": runCode, "Cmd-Enter": runCode, Tab: function (cm) { cm.replaceSelection("    "); } },
      placeholder: "在这里编写代码…",
    });
    cm.setOption("placeholder", "");
    return cm;
  }

  // ---------- 运行 ----------
  function setBusy(btn, busy, text) {
    if (!btn) return;
    if (busy) {
      btn.dataset.orig = btn.textContent;
      btn.textContent = text || "运行中…";
      btn.classList.add("btn-busy");
    } else {
      btn.textContent = btn.dataset.orig || btn.textContent;
      btn.classList.remove("btn-busy");
    }
  }

  function escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderOutput(el, resp) {
    el.innerHTML = "";
    if (!resp.ok) {
      if (resp.stage === "compile") {
        el.innerHTML = '<span class="err-text">编译错误</span>\n' + escHtml(resp.output || resp.error || "");
      } else {
        el.innerHTML = '<span class="err-text">运行失败</span>\n' + escHtml(resp.output || resp.error || "");
      }
      return;
    }
    var out = resp.output || "";
    el.textContent = out === "" ? "（无输出）" : out;
  }

  function post(path, data) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(function (r) { return r.json(); });
  }

  function runCode() {
    var code = srcEditor.getValue();
    if (!code.trim()) { flashOutput($("runOutput"), "请先在左侧编写代码"); return; }
    if (!ensureStdin(code, srcLang, $("runOutput"))) return;
    var btn = $("btnRun");
    setBusy(btn, true, "运行中…");
    $("runMeta").textContent = "";
    post("/api/run", { lang: srcLang, code: code, stdin: $("stdin").value })
      .then(function (resp) {
        renderOutput($("runOutput"), resp);
        var meta = $("runMeta");
        if (resp.ok) {
          meta.textContent = "退出码 " + resp.exit_code + " · " + resp.elapsed_ms + " ms";
          meta.className = "run-meta ok";
        } else {
          meta.textContent = (resp.stage === "compile" ? "编译失败" : "运行失败") + " · " + resp.elapsed_ms + " ms";
          meta.className = "run-meta err";
        }
      })
      .catch(function (e) {
        $("runOutput").innerHTML = '<span class="err-text">请求失败：' + escHtml(String(e)) + "</span>";
        $("runMeta").textContent = "";
      })
      .finally(function () { setBusy(btn, false); });
  }

  function runResult() {
    var code = dstEditor.getValue();
    if (!code.trim()) { flashOutput($("resultOutput"), "右侧还没有代码，请先转换"); return; }
    if (!ensureStdin(code, dstLang, $("resultOutput"))) return;
    var btn = $("btnRunResult");
    setBusy(btn, true, "运行中…");
    $("resultMeta").textContent = "";
    post("/api/run", { lang: dstLang, code: code, stdin: $("stdin").value })
      .then(function (resp) {
        renderOutput($("resultOutput"), resp);
        var meta = $("resultMeta");
        if (resp.ok) {
          meta.textContent = "退出码 " + resp.exit_code + " · " + resp.elapsed_ms + " ms";
          meta.className = "run-meta ok";
        } else {
          meta.textContent = (resp.stage === "compile" ? "编译失败" : "运行失败") + " · " + resp.elapsed_ms + " ms";
          meta.className = "run-meta err";
        }
      })
      .catch(function (e) {
        $("resultOutput").innerHTML = '<span class="err-text">请求失败：' + escHtml(String(e)) + "</span>";
      })
      .finally(function () { setBusy(btn, false); });
  }

  function flashOutput(el, msg) {
    el.innerHTML = '<span class="warn-text">' + escHtml(msg) + "</span>";
  }

  // ---------- 转换 ----------
  function convert(mode) {
    var code = srcEditor.getValue();
    if (!code.trim()) { flashOutput($("resultOutput"), "请先在左侧编写代码"); return; }
    var btn = mode === "ai" ? $("btnConvertAI") : $("btnConvert");
    setBusy(btn, true, mode === "ai" ? "AI 转换中…" : "转换中…");
    $("engineTag").textContent = "转换中…";
    var payload = { source: code, from: srcLang, to: dstLang };
    if (mode === "ai") {
      var cfg = loadConfig();
      payload.base_url = cfg.baseUrl;
      payload.api_key = cfg.apiKey;
      payload.model = cfg.model;
    }
    post(mode === "ai" ? "/api/convert_ai" : "/api/convert", payload)
      .then(function (resp) {
        if (resp.ok) {
          dstEditor.setValue(resp.code);
          $("engineTag").textContent = resp.engine === "ai" ? "已用 AI 转换" : "已用规则引擎转换";
          $("engineTag").className = "engine-tag " + resp.engine;
          flashOutput($("resultOutput"), resp.engine === "ai"
            ? "AI 转换完成，可直接运行。"
            : "规则引擎转换完成（适合教材常见语法，请人工核对后再使用）");
          dstEditor.focus();
        } else {
          $("engineTag").textContent = "转换失败";
          $("engineTag").className = "engine-tag";
          flashOutput($("resultOutput"), resp.error || "转换失败");
        }
      })
      .catch(function (e) {
        $("engineTag").textContent = "转换失败";
        flashOutput($("resultOutput"), "请求失败：" + String(e));
      })
      .finally(function () { setBusy(btn, false); });
  }

  // ---------- 其他操作 ----------
  function swap() {
    var tmpLang = srcLang, tmpCode = srcEditor.getValue();
    srcLang = dstLang; dstLang = tmpLang;
    srcEditor.setOption("mode", langById(srcLang).mode);
    dstEditor.setOption("mode", langById(dstLang).mode);
    srcEditor.setValue(dstEditor.getValue());
    dstEditor.setValue(tmpCode);
    $("srcLang").value = srcLang;
    $("dstLang").value = dstLang;
    $("engineTag").textContent = "已交换方向";
    $("engineTag").className = "engine-tag";
  }

  function copyResult() {
    var code = dstEditor.getValue();
    if (!code) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(function () {
        $("engineTag").textContent = "已复制";
        setTimeout(function () { $("engineTag").textContent = "已复制，可粘贴到编辑器对照"; }, 1600);
      });
    } else {
      var ta = document.createElement("textarea");
      ta.value = code;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      $("engineTag").textContent = "已复制";
    }
  }

  function loadSample(force) {
    if (force || !srcEditor.getValue().trim()) {
      srcEditor.setValue(TEMPLATES[srcLang] || "");
    } else {
      flashOutput($("runOutput"), "已保留你的代码；需要示例请点击「载入示例」前清空编辑器。");
    }
  }

  // ---------- 运行环境状态 ----------
  function loadEnv() {
    fetch("/api/env").then(function (r) { return r.json(); }).then(function (env) {
      var map = { c: "C", cpp: "C++", python: "Python", javascript: "JS" };
      var html = "";
      Object.keys(map).forEach(function (k) {
        var ok = env[k] && env[k].available;
        html += '<span class="pill ' + (ok ? "ok" : "missing") + '"><span class="dot"></span>' + map[k] + (ok ? " ✓" : " 未安装") + "</span>";
      });
      $("envPills").innerHTML = html;
    }).catch(function () {
      $("envPills").innerHTML = '<span class="pill missing"><span class="dot"></span>环境检测失败</span>';
    });
  }

  // ---------- AI 配置 ----------
  function loadConfig() {
    return {
      baseUrl: localStorage.getItem("cc_base_url") || "",
      apiKey: localStorage.getItem("cc_api_key") || "",
      model: localStorage.getItem("cc_model") || "deepseek-chat",
    };
  }
  function openSettings() {
    var c = loadConfig();
    $("cfgBaseUrl").value = c.baseUrl;
    $("cfgApiKey").value = c.apiKey;
    $("cfgModel").value = c.model;
    $("settingsMask").classList.remove("hidden");
  }
  function saveConfig() {
    localStorage.setItem("cc_base_url", $("cfgBaseUrl").value.trim());
    localStorage.setItem("cc_api_key", $("cfgApiKey").value.trim());
    localStorage.setItem("cc_model", $("cfgModel").value.trim() || "deepseek-chat");
    $("settingsMask").classList.add("hidden");
    flashOutput($("resultOutput"), "AI 配置已保存（仅保存在本机浏览器）。");
  }

  // ---------- 拖拽分隔条 ----------
  function initDivider() {
    var div = $("divider");
    var dragging = false;
    div.addEventListener("mousedown", function (e) {
      dragging = true;
      document.body.classList.add("resizing");
      div.classList.add("dragging");
      e.preventDefault();
    });
    document.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      var left = $("panelLeft"), right = $("panelRight");
      var total = left.offsetWidth + right.offsetWidth + div.offsetWidth;
      var pct = (e.clientX - left.getBoundingClientRect().left) / total * 100;
      pct = Math.max(25, Math.min(75, pct));
      left.style.flexBasis = pct + "%";
      right.style.flexBasis = (100 - pct) + "%";
    });
    document.addEventListener("mouseup", function () {
      if (!dragging) return;
      dragging = false;
      document.body.classList.remove("resizing");
      div.classList.remove("dragging");
    });
  }

  // ---------- 启动 ----------
  function init() {
    fillSelects();
    srcEditor = makeEditor($("srcEditor"), TEMPLATES[srcLang], langById(srcLang).mode);
    dstEditor = makeEditor($("dstEditor"), "", langById(dstLang).mode);
    $("btnRun").addEventListener("click", runCode);
    $("btnConvert").addEventListener("click", function () { convert("rule"); });
    $("btnConvertAI").addEventListener("click", function () {
      var c = loadConfig();
      if (!c.baseUrl || !c.apiKey) {
        flashOutput($("resultOutput"), "使用 AI 转换前，请先点击右上角「AI 设置」配置接口与 Key。");
        openSettings();
        return;
      }
      convert("ai");
    });
    $("btnSwap").addEventListener("click", swap);
    $("btnCopy").addEventListener("click", copyResult);
    $("btnRunResult").addEventListener("click", runResult);
    $("btnLoadSample").addEventListener("click", function () {
      srcEditor.setValue(TEMPLATES[srcLang] || "");
      $("runOutput").innerHTML = '<span class="console-placeholder">已载入示例，点击「运行」查看输出…</span>';
    });
    $("btnSettings").addEventListener("click", openSettings);
    $("btnCloseSettings").addEventListener("click", function () { $("settingsMask").classList.add("hidden"); });
    $("btnSaveConfig").addEventListener("click", saveConfig);
    $("btnClearConfig").addEventListener("click", function () {
      localStorage.removeItem("cc_base_url");
      localStorage.removeItem("cc_api_key");
      localStorage.removeItem("cc_model");
      $("cfgBaseUrl").value = "";
      $("cfgApiKey").value = "";
      $("cfgModel").value = "deepseek-chat";
      flashOutput($("resultOutput"), "AI 配置已清空。");
    });
    $("settingsMask").addEventListener("click", function (e) {
      if (e.target === $("settingsMask")) $("settingsMask").classList.add("hidden");
    });
    initDivider();
    loadEnv();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
