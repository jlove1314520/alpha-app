# -*- coding: utf-8 -*-
"""先.五十一-5 自我測試：IX0001 預估成交金額擷取與每日落地。
- 屬性有值 → 取屬性；只有 to_dict() 有 → 取 to_dict()；都沒有 → None（不拿 amount_sum 冒充）；
- 只有 TAIEX 會寫 estimate_amount_sum；落地每分鐘最多一筆。
用法：python scripts/selftest_shioaji_est_amount.py（純離線）。全部通過 exit 0。"""
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import shioaji_quotes as sq  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"：{detail}" if detail else ""))
    if not ok:
        fails.append(name)


class _DictOnly:
    def __init__(self, **kw):
        self.close, self.reference, self.amount_sum = "20000", "19900", "300000000000"
        self.datetime = kw.pop("dt")
        self._d = kw

    def to_dict(self):
        return dict(self._d)


def main() -> int:
    sq.EST_AMOUNT_DIR = Path(tempfile.mkdtemp(prefix="estamt_"))
    st = sq.TickState()
    st.live_state_path = None
    st.push_addr = None
    h = sq._make_quote_idx_handler(st, "TAIEX", "加權指數")

    q1 = SimpleNamespace(close="20000", reference="19900", amount_sum="300000000000",
                         estimate_amount_sum="520000000000", datetime=datetime(2026, 10, 8, 10, 0, 5))
    h(q1)
    snap = st.snapshot()["TAIEX"]
    check("屬性有值 → 寫 estimate_amount_sum", snap.get("estimate_amount_sum") == 5.2e11, str(snap.get("estimate_amount_sum")))
    check("同時寫 amount_sum", snap.get("amount_sum") == 3e11, str(snap.get("amount_sum")))

    h(_DictOnly(estimate_amount_sum="530000000000", dt=datetime(2026, 10, 8, 10, 0, 40)))
    check("只有 to_dict() → 仍取得", st.snapshot()["TAIEX"].get("estimate_amount_sum") == 5.3e11)

    st2 = sq.TickState()
    st2.live_state_path = None
    st2.push_addr = None
    h2 = sq._make_quote_idx_handler(st2, "TAIEX", None)
    h2(SimpleNamespace(close="20000", reference="19900", amount_sum="300000000000",
                       datetime=datetime(2026, 10, 8, 10, 1, 0)))
    check("拿不到預估值 → None（不以 amount_sum 冒充）", st2.snapshot()["TAIEX"].get("estimate_amount_sum") is None)

    h3 = sq._make_quote_idx_handler(st, "TPEX", None)
    h3(SimpleNamespace(close="250", reference="249", amount_sum="1", estimate_amount_sum="2",
                       datetime=datetime(2026, 10, 8, 10, 2, 0)))
    check("非 TAIEX 不寫預估成交金額", "estimate_amount_sum" not in st.snapshot().get("TPEX", {}))

    f = sq.EST_AMOUNT_DIR / "2026-10-08.jsonl"
    rows = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    check("落地每分鐘最多一筆（10:00 兩筆報價只落一筆，10:01 一筆）",
          [r["t"] for r in rows] == ["2026-10-08T10:00", "2026-10-08T10:01"], str([r["t"] for r in rows]))
    check("落地內容含預估值", rows[0].get("estimate_amount_sum") == 5.2e11, str(rows[0]))

    print("失敗：", "、".join(fails) if fails else "無")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
