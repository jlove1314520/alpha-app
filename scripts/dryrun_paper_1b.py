"""先.二十七-一：紙.一b 模擬日期 dry-run（2026-11-02 inception、2026-11-30 月底再平衡、重跑不重複）。
全程在沙盒目錄執行，並斷言正式紀錄檔／摘要／心跳檔的雜湊前後不變。"""
import hashlib, json, random, subprocess, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
TRACKER = ROOT / "research" / "paper_1b_tracker.py"
OFFICIAL = [ROOT / "research" / "data" / "paper_1b_log.jsonl", ROOT / "data" / "paper_1b.json",
            ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl"]
SYMS = ["0050", "00646", "00697B"]
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra else ""))
    if not cond:
        fails.append(name)


def h(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "ABSENT"


def synth_prices(real: dict, upto: str, path: Path) -> None:
    """真實序列到最後一筆，之後逐平日以固定種子隨機游走補到 upto（合成，僅供 dry-run）。"""
    rng = random.Random(20261102)
    out = {}
    for s in SYMS:
        rows = [dict(r) for r in real[s]]
        d = datetime.strptime(rows[-1]["date"], "%Y-%m-%d")
        px = rows[-1]["adj_close"]
        end = datetime.strptime(upto, "%Y-%m-%d")
        while d < end:
            d += timedelta(days=1)
            if d.weekday() >= 5:
                continue
            px *= 1 + rng.uniform(-0.01, 0.012)
            rows.append({"date": d.strftime("%Y-%m-%d"), "close": round(px, 4), "adj_close": round(px, 4)})
        out[s] = rows
    path.write_text(json.dumps({"prices": out}), encoding="utf-8")


def run(sb: Path, prices: Path, today: str):
    r = subprocess.run([sys.executable, str(TRACKER), "--dry-run", "--sandbox", str(sb), "--prices", str(prices),
                        "--today", today], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r


def rows(sb: Path):
    p = sb / "paper_1b_log.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


before = {p: h(p) for p in OFFICIAL}
real = json.loads((ROOT / "data" / "price_history.json").read_text(encoding="utf-8"))["prices"]
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    sb = td / "sb"
    # 0. 防呆：缺參數拒絕
    r0 = subprocess.run([sys.executable, str(TRACKER), "--dry-run"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("0 --dry-run 缺參數拒絕執行", r0.returncode != 0)
    # 1. 2026-11-02：建立 inception
    p1 = td / "p_1102.json"; synth_prices(real, "2026-11-02", p1)
    run(sb, p1, "2026-11-02")
    rs = rows(sb)
    check("1 11-02 建立 inception（僅 1 列）", len(rs) == 1 and rs[0]["event"] == "inception" and rs[0]["date"] == "2026-11-02", str([(x['date'], x['event']) for x in rs]))
    check("1b inception 權重 45/45/10", rs and rs[0]["targets"] == {"0050": 0.45, "00646": 0.45, "00697B": 0.10})
    # 2. 重跑不重複
    run(sb, p1, "2026-11-02")
    check("2 重跑不重複寫入", len(rows(sb)) == 1)
    # 3. 2026-11-30：月底再平衡（當日確認）
    p2 = td / "p_1130.json"; synth_prices(real, "2026-11-30", p2)
    r3 = run(sb, p2, "2026-11-30")
    rs = rows(sb)
    ev = [(x["date"], x["event"]) for x in rs]
    check("3 11-30 做月底再平衡（當日）", ev == [("2026-11-02", "inception"), ("2026-11-30", "month_end")], str(ev))
    if len(rs) == 2:
        m = rs[1]
        check("3b 月末後權重回到目標且成本>0", abs(m["weights_post"]["0050"] - 0.45) < 1e-9 and m["rebalance_cost"] > 0, f"cost={m['rebalance_cost']:.2f}")
        check("3c nav = nav_pre - cost", abs(m["nav"] - (m["nav_pre_rebalance"] - m["rebalance_cost"])) < 1e-6)
    # 4. 11-30 重跑不重複
    run(sb, p2, "2026-11-30")
    check("4 11-30 重跑不重複", len(rows(sb)) == 2)
    # 5. 同日再補到 12-01 資料：11-30 不得被重複記為月末
    p3 = td / "p_1201.json"; synth_prices(real, "2026-12-01", p3)
    run(sb, p3, "2026-12-01")
    ev = [(x["date"], x["event"]) for x in rows(sb)]
    check("5 12-01 後 11-30 仍只記一次", ev.count(("2026-11-30", "month_end")) == 1 and len(ev) == 2, str(ev))
    # 6. 摘要檔產生於沙盒
    check("6 沙盒摘要 started=true", json.loads((sb / "paper_1b.json").read_text(encoding="utf-8")).get("started") is True)
    # 7. 價格過期仍中止（11-30 用只到 11-02 的資料）
    sb2 = td / "sb2"
    run(sb2, p1, "2026-11-30")
    s2 = json.loads((sb2 / "paper_1b.json").read_text(encoding="utf-8")) if (sb2 / "paper_1b.json").exists() else {}
    check("7 價格過期中止並寫 last_error", (s2.get("last_error") or {}).get("status") == "ABORTED_STALE_PRICE")
after = {p: h(p) for p in OFFICIAL}
check("8 正式紀錄檔／摘要／心跳雜湊前後不變", before == after)
print(f"\n{'ALL PASS' if not fails else 'FAILED: ' + str(fails)}")
sys.exit(1 if fails else 0)
