# -*- coding: utf-8 -*-
"""先.一三五-1kh-n（2026-11-04）自測：DevQueue block 寫進 PENDING_QUEUE 前清掉控制字元。

不碰真檔（QUEUE／state／runner 寫檔紀錄全改指到暫存資料夾）。
1. _sanitize_ctrl_chars：BEL→「反斜線 a」、ESC→「反斜線 x1b」、CR／LF→空白、TAB 保留、乾淨字串原樣回傳。
2. mark_blocked()：原因含 BEL 與換行 → 寫出的檔沒有任何控制字元、阻塞條目仍是一行、後面的條目沒被拆開。
3. 守門員自己壞掉（傳入非字串）→ 不拋錯、照原物回傳（fail open）。
跑法：python scripts/selftest_dev_queue_block_ctrlchars.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import dev_queue_runner as D  # noqa: E402

fails = []
BS = chr(92)
BEL, ESC = chr(7), chr(27)


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


def has_ctrl(s):
    return any((ord(c) < 32 and c not in "\t\n") or ord(c) == 127 for c in s)


out, n = D._sanitize_ctrl_chars("C:" + BEL + "lpha" + ESC + "x\ty\r\nz")
check("1a BEL／ESC 換成可見文字、TAB 保留、CR／LF 換空白",
      out == "C:" + BS + "alpha" + BS + "x1bx\ty  z" and n == 4, repr(out))
out2, n2 = D._sanitize_ctrl_chars("乾淨的一行")
check("1b 乾淨字串原樣回傳", out2 == "乾淨的一行" and n2 == 0)

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    q = td / "PENDING_QUEUE.md"
    q.write_text("# 佇列\n- [ ] **先.測試-1 第一項** [維運]（DevQueue 可執行）\n- [ ] **先.測試-2 第二項** [維運]\n",
                 encoding="utf-8", newline="\n")
    D.QUEUE = q
    D._record_runner_write = lambda *a, **k: None
    D._load_state = lambda: {}
    D._save_state = lambda st: None
    _orig_find = D.find_next
    D.find_next = lambda: (1, q.read_text(encoding="utf-8").split("\n")[1])
    rc = D.mark_blocked("路徑 C:" + BEL + "lpha 不見\n第二行")
    D.find_next = _orig_find
    txt = q.read_text(encoding="utf-8")
    lines = txt.split("\n")
    check("2a mark_blocked 回 0", rc == 0, str(rc))
    check("2b 寫出的檔沒有控制字元", not has_ctrl(txt), repr(txt[:200]))
    check("2c 阻塞條目仍是一行且含可見的反斜線 a",
          lines[1].startswith("- [!]") and ("C:" + BS + "alpha") in lines[1] and "第二行" in lines[1], lines[1][-60:])
    check("2d 第二項沒被拆開", lines[2] == "- [ ] **先.測試-2 第二項** [維運]", lines[2])

r, n3 = D._sanitize_ctrl_chars(None)  # type: ignore[arg-type]
check("3 守門員自己壞掉不拋錯、照原物回傳", r is None and n3 == 0)

print("PASS" if not fails else f"FAIL {len(fails)} 項：{fails}")
sys.exit(1 if fails else 0)
