"""排程啟動檔編碼自測（先.九十七-R1，2026-10-14 DevQueue 20261014-233102）。

根因（先.九十七-1）：C:\\alpha 下 5 支 run-*.ps1 存成無 BOM 的 UTF-8，Windows PowerShell 5.1
遇到沒有 BOM 的檔案會用系統字碼頁（cp950）讀，中文註解把下一行 `$repoDir = ...` 吃掉，
排程回報 0 卻一行都沒跑。

檢查兩件事：
1. 靜態（快，只用標準函式庫）：「含非 ASCII 位元組且開頭沒有 UTF-8 BOM」→ FAIL。
2. --parse（慢，呼叫一次 powershell）：同一支檔分別用「PowerShell 預設讀法（ParseFile，
   無 BOM 時走 cp950）」與「強制 UTF-8」解析，頂層敘述數或語法錯誤數不同 → FAIL。

用法：python scripts/selftest_launcher_encoding.py [--parse] [--json]
結束碼：全過 0、有 FAIL 1。被看門狗 import 時只呼叫 scan_bom()，不會中斷呼叫端（CLAUDE.md 十二節）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception as e:  # 舊版 Python／被重導向時沒有 reconfigure，照常輸出
    print(f"[selftest_launcher_encoding] reconfigure 失敗，略過：{e}", file=sys.stderr)

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
BOM = b"\xef\xbb\xbf"


def launcher_files() -> list[Path]:
    files = sorted(ROOT.glob("*.ps1")) + sorted((APP / "scripts").glob("*.ps1"))
    return [p for p in files if p.is_file()]


def scan_bom(files: list[Path] | None = None) -> list[dict]:
    """回傳每支檔的 {file, non_ascii, bom, ok}。含非 ASCII 但沒有 BOM 判 ok=False。"""
    out = []
    for p in files if files is not None else launcher_files():
        b = p.read_bytes()
        bom = b.startswith(BOM)
        non_ascii = any(x > 0x7F for x in (b[3:] if bom else b))
        out.append({"file": str(p), "non_ascii": non_ascii, "bom": bom, "ok": bom or not non_ascii})
    return out


_PS = r"""
$ErrorActionPreference = 'Stop'
$res = @()
foreach ($f in ($env:ALPHA_PS1_FILES -split '\|')) {
  $t1 = $null; $e1 = $null; $t2 = $null; $e2 = $null
  $a1 = [System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$t1, [ref]$e1)
  $txt = [System.IO.File]::ReadAllText($f, [System.Text.Encoding]::UTF8)
  $a2 = [System.Management.Automation.Language.Parser]::ParseInput($txt, [ref]$t2, [ref]$e2)
  $res += [pscustomobject]@{ file = $f; default_stmts = $a1.EndBlock.Statements.Count; default_errs = $e1.Count;
                             utf8_stmts = $a2.EndBlock.Statements.Count; utf8_errs = $e2.Count }
}
$res | ConvertTo-Json -Compress
"""


def parse_compare(files: list[Path]) -> list[dict]:
    """一次 powershell 呼叫比對全部檔案的兩種讀法。"""
    if not files:
        return []
    # -Command 收不到額外參數，檔案清單走環境變數（路徑不含 |）
    env = dict(os.environ, ALPHA_PS1_FILES="|".join(map(str, files)))
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS],
                       capture_output=True, timeout=180, env=env)
    raw = r.stdout.decode("utf-8", errors="replace").strip()
    if r.returncode != 0 or not raw:
        raise RuntimeError(f"powershell 解析失敗（exit {r.returncode}）：{r.stderr.decode('utf-8', 'replace')[:300]}")
    data = json.loads(raw)
    rows = data if isinstance(data, list) else [data]
    for x in rows:
        x["ok"] = x["default_stmts"] == x["utf8_stmts"] and x["default_errs"] == x["utf8_errs"]
    return rows


def main() -> int:
    do_parse = "--parse" in sys.argv
    files = launcher_files()
    bom_rows = scan_bom(files)
    parse_rows = parse_compare(files) if do_parse else []
    bad_bom = [r for r in bom_rows if not r["ok"]]
    bad_parse = [r for r in parse_rows if not r["ok"]]
    if "--json" in sys.argv:
        print(json.dumps({"bom": bom_rows, "parse": parse_rows}, ensure_ascii=False, indent=1))
    print(f"排程啟動檔編碼自測：掃 {len(files)} 支 .ps1；含中文 {sum(r['non_ascii'] for r in bom_rows)} 支、"
          f"有 BOM {sum(r['bom'] for r in bom_rows)} 支")
    for r in bad_bom:
        print(f"  FAIL 含非 ASCII 但沒有 UTF-8 BOM：{r['file']}")
    if do_parse:
        print(f"  PowerShell 兩種讀法比對 {len(parse_rows)} 支")
        for r in bad_parse:
            print(f"  FAIL 讀法不同：{r['file']}（預設 {r['default_stmts']} 敘述／{r['default_errs']} 錯誤；"
                  f"UTF-8 {r['utf8_stmts']} 敘述／{r['utf8_errs']} 錯誤）")
    ok = not bad_bom and not bad_parse
    print("全部通過" if ok else "有 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
