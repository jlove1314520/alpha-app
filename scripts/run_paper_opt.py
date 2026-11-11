# -*- coding: utf-8 -*-
"""先.一五四-1c（2026-11-08 DevQueue 20261108-140101）：紙上優化軌每日本機執行（掛在既有本機排程 AlphaPaper9 週一～五 18:30 後面）。

為什麼不照條目原文掛 market.yml：research/paper_opt_track.py 與各成員產生器讀的 research/data/drawdown_fix、panic_pq、
paper_opt/ 都被 .gitignore 排除（只在本機），雲端跑會沒有輸入。〔自行裁量〕不新增 Windows 排程（新增要總司令本人操作），
改由 scripts/run_paper_9.ps1 跑完模擬 I 之後呼叫本支。

做法：
0. 先跑 research/fetch_paper_opt_us_prices.py（先.一五四-1d 甲①，美股成員價格，yfinance 每日 ≤1 次）與
   research/fetch_paper_opt_odd_lot.py（甲②，TWSE TWTC7U 每日 ≤1 次）；只有這兩步會送外部請求。
1. 依序跑 research/paper_opt_{pq,f11,f12,f14,f17,f15,f16,f18}.py（各自獨立子行程、各 15 分鐘逾時；一支失敗只記警告，不影響其他支）。
   各產生器只處理還沒寫過的交易日、11/09 前不寫帳本、零外部請求（見各檔檔頭）。
1a. 跑 research/paper_opt_regime.py（F3／F5／F2／F3F5，收件匣 042，零外部請求，只讀 f12 日線快取所以排在 f12 之後）、
    research/paper_opt_stock.py（個股 S1～S4／S1x15／S1x2／S1S3F14，收件匣 043，零外部請求，組合讀 F14 帳本所以排在 f14 之後）。
1b. 跑 research/paper_opt_arena.py（台股擂台跟單 A～D，零外部請求）、research/paper_opt_ntsf.py（國安基金護盤 NTSF-A／B，零外部請求）、research/paper_opt_ntsf_c.py（NTSF-C，零外部請求）與 research/paper_opt_combo.py（組合 C25／C20／C15 合成，零外部請求）。
2. 跑 research/paper_opt_track.py 重算 data/paper_opt_track.json（零外部請求）。
3. 有變動才用 scripts/local_git_commit.commit_paths() 只提交 data/paper_opt_track.json（十節：在 MACHINE_WRITTEN ^data/ 樣式內）。
   各成員帳本 research/data/paper_opt/ledger_*.jsonl 只留本機（同其他 research/data 快取），不提交。
十二節：任何失敗只印警告、exit 0。
跑法：python scripts/run_paper_opt.py [--no-commit]
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

GENERATORS = ["pq", "f11", "f12", "f14", "f17", "f15", "f16", "f18"]
# 先.一五四-1d 甲①：美股成員先抓價（每日最多 1 次 yfinance 批次，同台北日期已抓就零請求）
PRE_FETCH = ["research/fetch_paper_opt_us_prices.py", "research/fetch_paper_opt_odd_lot.py"]  # 甲②：TWTC7U 每日最多 1 次
SUMMARY = "data/paper_opt_track.json"
TIMEOUT_SEC = 900


def _run(rel: str) -> bool:
    path = ROOT / rel
    if not path.exists():
        print(f"[warn] 找不到 {rel}，略過")
        return False
    try:
        p = subprocess.run([sys.executable, str(path)], cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_SEC)
        tail = "\n".join((p.stdout or "").strip().splitlines()[-5:])
        print(f"== {rel} exit={p.returncode}\n{tail}")
        if p.returncode != 0:
            print(f"[warn] {rel} 非零結束：{(p.stderr or '').strip()[-500:]}")
        return p.returncode == 0
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {rel} 執行失敗：{type(e).__name__}: {e}")
        return False


def main() -> int:
    no_commit = "--no-commit" in sys.argv[1:]
    for rel in PRE_FETCH:
        _run(rel)
    ok = {g: _run(f"research/paper_opt_{g}.py") for g in GENERATORS}
    ok["regime"] = _run("research/paper_opt_regime.py")  # 先.一五八-1（收件匣 042）：F3／F5／F2／F3F5；只讀 f12_bars 快取，必須排在 f11／f12 之後
    ok["stock"] = _run("research/paper_opt_stock.py")  # 先.一五九-1（收件匣 043）：個股 S1～S4＋加碼版＋S1S3F14；組合讀 F14 帳本，必須排在 f14 之後
    ok["arena"] = _run("research/paper_opt_arena.py")  # 先.一五六-1b：台股擂台跟單 A～D 四版（帳本只留本機；總表／App 顯示見 先.一五六-1c）
    ok["ntsf"] = _run("research/paper_opt_ntsf.py")  # 先.一五六-2 ④：國安基金第 10 次護盤 NTSF-A／B（零外部請求，帳本只留本機）
    ok["ntsf_c"] = _run("research/paper_opt_ntsf_c.py")  # 先.一五六-2b：NTSF-C（F12 名單 2× 停利 15%，零外部請求，帳本只留本機）
    ok["combo"] = _run("research/paper_opt_combo.py")  # 先.一五四-1a ⑦：組合 C25／C20／C15 用成員原版紙上報酬合成（要在各成員之後）
    track_ok = _run("research/paper_opt_track.py")
    print(f"產生器結果：{ok}；總表：{'OK' if track_ok else '失敗'}")
    if no_commit or not track_ok:
        return 0
    try:
        import local_git_commit as G  # noqa: PLC0415
        msg = (f"紙上優化軌本機排程更新 {datetime.now():%Y-%m-%d %H:%M}\n\n"
               "scripts/run_paper_opt.py（掛在 AlphaPaper9 後面）只提交 data/paper_opt_track.json；"
               "該檔在 MACHINE_WRITTEN ^data/ 樣式內（十節）。紙上追蹤，非投資建議。")
        print(G.commit_paths([SUMMARY], msg))
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 紙上優化軌提交失敗（下一輪再試）：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
