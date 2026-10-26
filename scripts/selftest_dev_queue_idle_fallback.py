# -*- coding: utf-8 -*-
"""先.一三五-1（2026-10-27，收件匣 024）自測：DevQueue 沒有可執行項目時的「24 小時預設放行」與「連續 2 輪空轉 → 候選補件」。
不碰真檔（AWAITING／提示詞檔都改指到暫存資料夾）。
1. 預設放行候選：等 30 小時的乾淨列入選；等 5 小時的不選；含 holdout／請總司令／非阻塞的不選；「21:2x」這種時間寫法能解析。
2. 連續空轉輪數：…OK、QUEUE_EMPTY、YIELD、GATED → 2（YIELD 不算也不打斷）；最後一輪 OK → 0。
3. _idle_fallback_prompt()：有候選 → 寫預設放行提示詞、回 True；沒候選但連續 2 輪空轉 → 寫候選補件提示詞、回 True；都沒有 → False。
跑法：python scripts/selftest_dev_queue_idle_fallback.py
"""
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import dev_queue_runner as D  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


now = datetime(2026, 10, 27, 6, 30, tzinfo=D.TZ)
AW = """# 等待
## 等待中（目前：5件）

| 項目 | 完成時間 | 等待審閱內容 | 等待時長 |
|---|---|---|---|
| 先.甲 前向草稿 | 2026-10-26 00:2x | 草稿：建議甲 | 自 00:2x 起 |
| 先.乙 新草稿 | 2026-10-27 01:30 | 草稿 | 自 01:30 起 |
| 先.丙 要讀 holdout | 2026-10-25 10:00 | 讀 holdout 期間資料 | 自 10:00 起 |
| 先.丁 請總司令執行排程 | 2026-10-24 09:00 | 請總司令執行 | 自 09:00 起 |
| 先.戊（非阻塞、方便時再做） | 2026-10-24 09:00 | 方便時 | 非阻塞 |

## 等前置條件
"""
c = D._default_release_candidates(now, AW)
check("1 只選等 >24 小時且不碰排除類別的列（含 21:2x 寫法）", [x[0] for x in c] == ["先.甲 前向草稿"], str(c))

log = "\n".join(f"===== DevQueue cycle end: 2026-10-27 0{i}:01:02 cycle_id=x reason={r} exit=0 duration_min=0 ====="
                for i, r in enumerate(["OK", "QUEUE_EMPTY", "YIELD", "GATED"]))
check("2a 連續空轉 2 輪（YIELD 不算不打斷）", D._consecutive_idle_rounds(log) == 2, str(D._consecutive_idle_rounds(log)))
check("2b 最後一輪 OK → 0", D._consecutive_idle_rounds(log + "\n===== DevQueue cycle end: x y cycle_id=z reason=OK exit=0 =====") == 0)

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    _state = {}
    D._load_state = lambda: _state
    D._save_state = lambda st: None
    D.PROMPT_OUT = td / "prompt.txt"
    D.AWAIT_FILE = td / "aw.md"
    D.AWAIT_FILE.write_text(AW, encoding="utf-8")
    real_c = D._default_release_candidates
    D._default_release_candidates = lambda now=None, text=None: real_c(datetime(2026, 10, 27, 6, 30, tzinfo=D.TZ), text)
    D._consecutive_idle_rounds = lambda log_text=None: 0
    ok = D._idle_fallback_prompt() and "24 小時預設放行" in D.PROMPT_OUT.read_text(encoding="utf-8") and "先.甲 前向草稿" in D.PROMPT_OUT.read_text(encoding="utf-8")
    check("3a 有候選 → 預設放行提示詞", ok)
    D._consecutive_idle_rounds = lambda log_text=None: 0
    check("3d 同一項 24 小時內不重試（趕工迴圈不會無限派同一項）", D._idle_fallback_prompt() is False)
    D.AWAIT_FILE.write_text(AW.replace("2026-10-26 00:2x", "2026-10-27 05:00"), encoding="utf-8")
    D._consecutive_idle_rounds = lambda log_text=None: 2
    ok = D._idle_fallback_prompt() and "候選補件" in D.PROMPT_OUT.read_text(encoding="utf-8")
    check("3b 沒候選、連續 2 輪空轉 → 候選補件提示詞", ok)
    check("3e 候選補件每小時最多一次", D._idle_fallback_prompt() is False)
    D._consecutive_idle_rounds = lambda log_text=None: 1
    check("3c 都沒有 → 不派工（照舊 QUEUE_EMPTY）", D._idle_fallback_prompt() is False)

print(f"\n結果：{'全部通過' if not fails else '失敗 ' + str(fails)}")
sys.exit(1 if fails else 0)
