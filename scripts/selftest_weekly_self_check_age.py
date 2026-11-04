"""自測：週報 system_health 的自檢新鮮度看 self_check.checked_at，不借頂層 generated_at（先.一三五-1kh）。
零外部請求：暫存目錄放假的 data/audit_report.json，把模組 ROOT 指過去。"""
import sys, json, tempfile
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_weekly_report as W

now = datetime(2026, 11, 4, 10, 0, tzinfo=W.TZ)
res = []
def case(label, top_h, sc_h, expect_lvl, expect_note):
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "data").mkdir()
        sc = {"ok": True, "checks": []}
        if sc_h is not None:
            sc["checked_at"] = (now - timedelta(hours=sc_h)).isoformat()
        doc = {"generated_at": (now - timedelta(hours=top_h)).isoformat(), "gate_pass": True, "self_check": sc,
               "local_task_health": {"stalled": []}}
        (Path(td) / "data" / "audit_report.json").write_text(json.dumps(doc), encoding="utf-8")
        old = W.ROOT; W.ROOT = Path(td)
        try:
            h = W.sec_system_health(now)
        finally:
            W.ROOT = old
        line = W.summary_lines({"system_health": h})[0]
        ok = h["level"] == expect_lvl and (("沒更新" in line) == expect_note)
        res.append((label, ok, f'level={h["level"]} age={h.get("self_check_age_hours")} line={line}'))

case("頂層新、自檢也新 → ok、不加註", 11, 27, "ok", False)
case("頂層新（本機 23:00）、自檢 72 小時前（雲端停擺）→ warn＋加註", 11, 72, "warn", True)
case("自檢沒有 checked_at → fail open 不加註", 11, None, "ok", False)
case("頂層舊 60 小時 → warn（既有行為不變）", 60, 27, "warn", False)
for l, ok, d in res:
    print(("PASS" if ok else "FAIL"), l, "｜", d)
nf = sum(1 for _, ok, _ in res if not ok)
print(f"合計 {len(res)} 項，失敗 {nf}")
sys.exit(1 if nf else 0)
