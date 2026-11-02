"""版控文字檔不得含 ASCII 控制字元（先.一三五-1go，2026-11-01）。

背景：自走輪次用 Python／shell 寫檔時，`C:\\alpha` 的 `\\a`、正則的 `\\b`、路徑的 `\\f`
常被當成跳脫字元，變成 BEL(0x07)／backspace(0x08)／form feed(0x0c)。文件裡只是路徑壞掉，
但寫進正則就是「永遠不命中」的安靜失效（冒煙 #72、selection_bias_ledger 分軌退路都中過）。

掃 `git ls-files` 的文字檔，有 0x00～0x1f（tab／LF／CR 除外）就列出檔名行號、exit 1。
零外部請求、唯讀。

第二段（先.一三五-1gr）：檔案裡看起來正常的非 raw 字串 `"C:\\alpha"`，執行時 `\\a` 才變 BEL，
第一段的檔案掃描抓不到；改用 `ast` 解析 .py，檢查字串常數的「執行時值」有無控制字元。
"""
import ast
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # 主控台不支援 reconfigure 時照常跑，只是中文可能亂碼
    print(f"[warn] reconfigure 失敗：{e}")

ROOT = Path(__file__).resolve().parent.parent
EXTS = (".md", ".py", ".ps1", ".mjs", ".js", ".yml", ".yaml", ".html")
BAD = set(range(32)) - {9, 10, 13}


def scan_text(text: str) -> list[tuple[int, list[str]]]:
    """回傳 [(行號, [控制字元十六進位...])]。"""
    out = []
    for n, line in enumerate(text.split("\n"), 1):
        cs = [hex(ord(c)) for c in line if ord(c) in BAD]
        if cs:
            out.append((n, cs))
    return out


fails = []


def check(name: str, ok: bool) -> None:
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails.append(name)


# 反向驗證：防止掃描被改成永遠不命中／永遠命中
check("合成：含 BEL 的路徑必須命中", bool(scan_text("清單在 `C:" + chr(7) + "lpha` 裡")))
check("合成：正則裡的 backspace 必須命中", bool(scan_text('re.search(r"' + chr(8) + 'fut_", s)')))
check("合成：正常反斜線＋tab＋CRLF 不得命中", not scan_text("C:\\alpha\\b\tx\r\ny"))

files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stdout.split("\n")
hits = []
for f in files:
    if not f.endswith(EXTS):
        continue
    try:
        t = (ROOT / f).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue  # 非 UTF-8 或已刪檔不屬本測範圍
    for n, cs in scan_text(t):
        hits.append(f"{f}:{n} {cs}")
for h in hits:
    print("  命中 " + h)
check(f"版控文字檔無控制字元（命中 {len(hits)} 行）", not hits)


def scan_ast(src: str) -> list[tuple[int, list[str]]]:
    """回傳 [(行號, [控制字元十六進位...])]：字串常數執行時值含控制字元者。"""
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            cs = sorted({hex(ord(c)) for c in node.value if ord(c) in BAD})
            if cs:
                out.append((node.lineno, cs))
    return out


# 反向驗證（原始碼文字用 chr(92) 組出反斜線，避免本檔自己被 AST 段命中）
BS = chr(92)
check("合成 AST：非 raw 的 \"C:" + BS + "alpha\" 必須命中", bool(scan_ast('p = "C:' + BS + 'alpha"')))
check("合成 AST：raw 的 r\"C:" + BS + "alpha\" 不得命中", not scan_ast('p = r"C:' + BS + 'alpha"'))
check("合成 AST：tab／換行跳脫不得命中", not scan_ast('p = "a' + BS + 't' + BS + 'n"'))

ast_hits = []
for f in files:
    if not f.endswith(".py"):
        continue
    try:
        src = (ROOT / f).read_text(encoding="utf-8")
        found = scan_ast(src)
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as e:
        print(f"  [warn] 略過 {f}：{type(e).__name__}")  # 無法解析不屬本測範圍
        continue
    for n, cs in found:
        ast_hits.append(f"{f}:{n} {cs}")
for h in ast_hits:
    print("  AST 命中 " + h)
check(f".py 字串常數執行時無控制字元（命中 {len(ast_hits)} 處）", not ast_hits)


# 第三段（先.一三五-1io）：行中間的單獨 CR。`read_text()` 預設把單獨 CR 當換行吃掉，第一段看不到；
# 實例：run_warrant_snapshot.ps1 的 "$repoDir\research" 被寫成 $repoDir＋CR＋esearch，Test-Path 永遠假。
def scan_lone_cr(raw: bytes) -> list[int]:
    """回傳含「後面不是 LF 的 CR」的行號。"""
    out = []
    for n, line in enumerate(raw.split(b"\n"), 1):
        body = line[:-1] if line.endswith(b"\r") else line
        if b"\r" in body:
            out.append(n)
    return out


check("合成：路徑中間的單獨 CR 必須命中", bool(scan_lone_cr(b'x = "$repoDir' + bytes([13]) + b'esearch"\r\n')))
check("合成：CRLF 與 LF 換行不得命中", not scan_lone_cr(b"a\r\nb\nc\r\n"))

cr_hits = []
for f in files:
    # 存檔的官方原始回應 HTML（research/*_probe*.html）本來就含單獨 CR，不是我們寫的程式；只掃程式與文件
    if not (f.endswith(tuple(e for e in EXTS if e != ".html")) or f == "index.html"):
        continue
    try:
        raw = (ROOT / f).read_bytes()
    except OSError:
        continue  # 已刪檔不屬本測範圍
    for n in scan_lone_cr(raw):
        cr_hits.append(f"{f}:{n}")
for h in cr_hits:
    print("  單獨 CR 命中 " + h)
check(f"版控文字檔無行中單獨 CR（命中 {len(cr_hits)} 行）", not cr_hits)



# 第四段（先.一三五-1ir）：排程真正呼叫的入口腳本在 repo 外（`C:\alpha\run-*.ps1`／`register-*.ps1`／`*.bat`），
# 不在 git ls-files 裡。用位元組掃（.bat 可能是 cp950，多位元組尾碼都 ≥0x40 不會誤判）；UTF-16 BOM 先解碼。
# 資料夾不存在只印 [warn] 略過、不 FAIL（十二節：守門員自己的失敗只降級）。
def scan_outside_bytes(raw: bytes) -> tuple[list[tuple[int, list[str]]], list[int]]:
    """回傳（控制字元命中, 單獨 CR 行號）。"""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        raw = raw.decode("utf-16").encode("utf-8")
    ctrl = []
    for n, line in enumerate(raw.split(b"\n"), 1):
        cs = [hex(b) for b in line if b in BAD]
        if cs:
            ctrl.append((n, cs))
    return ctrl, scan_lone_cr(raw)


check("合成 repo 外：含 BEL 的 .ps1 必須命中",
      bool(scan_outside_bytes(b'$p = "C:' + bytes([7]) + b'lpha"\r\n')[0]))
check("合成 repo 外：UTF-16 BOM 的正常 .ps1 不得命中",
      scan_outside_bytes("cd C:\\alpha\r\n".encode("utf-16")) == ([], []))

OUTSIDE = ROOT.parent
out_hits = []
try:
    outside_files = sorted(p for p in OUTSIDE.iterdir() if p.is_file() and p.suffix.lower() in (".ps1", ".bat"))
except OSError as e:
    outside_files = []
    print(f"  [warn] 讀不到 {OUTSIDE}，略過第四段：{type(e).__name__}")
for p in outside_files:
    try:
        ctrl, crs = scan_outside_bytes(p.read_bytes())
    except (OSError, UnicodeDecodeError) as e:
        print(f"  [warn] 略過 {p.name}：{type(e).__name__}")
        continue
    out_hits += [f"{p.name}:{n} {cs}" for n, cs in ctrl] + [f"{p.name}:{n} 單獨CR" for n in crs]
for h in out_hits:
    print("  repo 外命中 " + h)
check(f"repo 外入口腳本 {OUTSIDE}\\*.ps1／*.bat（{len(outside_files)} 支）無控制字元與單獨 CR（命中 {len(out_hits)} 處）",
      not out_hits)

print("失敗：" + ("、".join(fails) if fails else "無"))
sys.exit(1 if fails else 0)
