# -*- coding: utf-8 -*-
"""先.一三五-1fh 自測：冒煙等待條件掃描（scan_smoke_waits.main，冒煙 #127 的守門員）。

模組的 SMOKE／INDEX 換成合成字串，只讀不寫、零外部請求。
用法：python scripts/selftest_scan_smoke_waits.py
"""
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import scan_smoke_waits as S  # noqa: E402

results = []


def check(name, ok):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name)


def wait(rx, el, flags="", sel="id"):
    getter = f'document.getElementById("{el}")' if sel == "id" else f'document.querySelector("#{el}")'
    return f"await page.waitForFunction(() => /{rx}/{flags}.test({getter}.textContent), null, {{timeout: 5000}});\n"


def run(smoke, index):
    S.SMOKE, S.INDEX = smoke, index
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = S.main()
    return rc, buf.getvalue()


IDX = ('<div id="note">來源：日收盤價</div>'
       '<span id="mk">nyse</span>'
       '<div id="outer"><div>內層</div>載入中</div>')

rc, out = run(wait("來源：", "note"), IDX)
check("預設文字已符合等待 → 列可疑 exit 1", rc == 1 and "#note" in out)

rc, out = run(wait("來源：官方", "note"), IDX)
check("預設文字不符合 → exit 0", rc == 0 and "沒有發現" in out)

rc, out = run(wait("來源：", "note", sel="qs"), IDX)
check("querySelector(\"#id\") 形狀也抓到", rc == 1 and "#note" in out)

rc, out = run(wait("載入中", "outer"), IDX)
check("巢狀同名標籤取到完整預設文字（含內層之後的文字）", rc == 1 and "#outer" in out)
check("default_text 去標籤後內容正確", S.default_text("outer") == "內層載入中")

rc, out = run(wait("^NYSE$", "mk", flags="i"), IDX)
check("JS 正則 i 旗標（大小寫不分）照樣套用 → 抓到", rc == 1 and "#mk" in out)

rc, out = run(wait("^NYSE$", "mk"), IDX)
check("沒有 i 旗標 → 大小寫不同不算符合", rc == 0)

rc, out = run(wait("(?<x>a)", "note") + wait("來源：", "note"), IDX)
check("Python 編不過的正則只略過＋警告，後面照常掃", rc == 1 and "warn" in out and "#note" in out)

rc, out = run(wait("來源：", "不存在"), IDX)
check("index.html 沒有該元素 → 不算檢查、不列可疑", rc == 0 and "檢查了 0 組" in out)

print(f"合計 {len(results)} 項，失敗 {results.count(False)}")
sys.exit(1 if False in results else 0)
