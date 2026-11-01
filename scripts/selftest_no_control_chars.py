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

print("失敗：" + ("、".join(fails) if fails else "無"))
sys.exit(1 if fails else 0)
