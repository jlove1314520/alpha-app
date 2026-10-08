# -*- coding: utf-8 -*-
"""先.五十一-6 自我測試：shioaji_quotes.py 的 faulthandler 與當日重啟次數。
- _mark_restart_state：上一個行程沒正常收尾（running 仍 True）→ 異常重啟 +1；跨日歸零；壞檔不拋例外；
- 子行程實際觸發一次原生崩潰（faulthandler._sigsegv），確認堆疊寫進指定 log 且行程非零退出。
用法：python scripts/selftest_shioaji_restart.py（純離線）。全部通過 exit 0。"""
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import shioaji_quotes as sq  # noqa: E402

TZ = timezone(timedelta(hours=8))
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"：{detail}" if detail else ""))
    if not ok:
        fails.append(name)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="sqrestart_"))
    p = tmp / "restart.json"
    d1 = datetime(2026, 10, 9, 8, 30, tzinfo=TZ)

    st = sq._mark_restart_state(True, d1, p)
    check("首次啟動：starts=1、異常=0", st.get("starts_today") == 1 and st.get("abnormal_restarts_today") == 0, str(st))
    st = sq._mark_restart_state(True, d1 + timedelta(minutes=30), p)
    check("上一個行程未收尾又啟動：異常=1", st.get("abnormal_restarts_today") == 1 and st.get("starts_today") == 2, str(st))
    sq._mark_restart_state(False, d1 + timedelta(hours=5), p)
    st = sq._mark_restart_state(True, d1 + timedelta(hours=5, minutes=1), p)
    check("正常收尾後再啟動：異常不增加", st.get("abnormal_restarts_today") == 1 and st.get("starts_today") == 3, str(st))
    st = sq._mark_restart_state(True, d1 + timedelta(days=1), p)
    check("跨日歸零", st.get("starts_today") == 1 and st.get("abnormal_restarts_today") == 0, str(st))
    p.write_text("{壞掉", encoding="utf-8")
    try:
        st = sq._mark_restart_state(True, d1, p)
        check("壞檔不拋例外並重建", st.get("starts_today") == 1, str(st))
    except Exception as e:  # noqa: BLE001
        check("壞檔不拋例外並重建", False, type(e).__name__)

    log = tmp / "fault.log"
    code = (
        "import sys; sys.path.insert(0, r'%s'); import shioaji_quotes as sq; from pathlib import Path; "
        "sq.FAULT_LOG_PATH = Path(r'%s'); f = sq._enable_faulthandler(); "
        "import faulthandler; faulthandler._sigsegv()" % (ROOT / "research", log)
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=120)
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    check("原生崩潰時行程非零退出", r.returncode != 0, f"returncode={r.returncode}")
    check("faulthandler 把崩潰堆疊寫進 log", "Fatal Python error" in text and "啟動" in text, text[:160].replace("\n", " | "))

    print("失敗：", "、".join(fails) if fails else "無")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
