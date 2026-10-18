# -*- coding: utf-8 -*-
"""先.一一三-A3（2026-10-18 總司令裁示）：每個交易日 20:30，本機與雲端各檢查一次台股當日資料有沒有進來。

判定：今天（台北）是台股交易日（data/trading_calendar.json；讀不到就照週一～五）、時間已過 20:30，
而 data/market_tw.json 的 data_date 不是今天 → 告警：「今日台股資料未進來，三層備援都沒補到」。
（三層＝雲端 market.yml 17:13／18:41、本機 AlphaMarketCatchup 17:30／19:30、雲端 watchdog 17:45 後補觸發。）

告警時：
- 寫 data/tw_data_alarm.json（App 讀它亮紅色橫幅；App 自己也會用 market_tw＋交易日曆再算一次，不只靠這個檔）；
- 雲端（--layer cloud）：exit 1，讓 job 紅燈 → GitHub email／手機 App 的 Actions 失敗推播；
- 本機（--layer local）：commit＋push 告警檔，並 `gh workflow run tw_data_landed_check.yml`（雲端排程常被延後或跳過，
  由本機補叫一次，讓失敗推播一定發得出去）。
沒告警時：若告警檔記的是「今天有告警」就改成解除；其餘情況不寫檔（不製造沒有內容變化的 commit）。

十二節：本腳本自身任何例外只印 ::warning:: 並 exit 0，不得讓被監控的流程（或 watchdog）跟著失敗。
用法：python scripts/check_tw_data_landed.py --layer cloud|local [--now 2026-10-19T20:31:00+08:00]（測試用）
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
TW = timezone(timedelta(hours=8))
CHECK_HM = (20, 30)
ALARM_PATH = ROOT / "data" / "tw_data_alarm.json"
MESSAGE = "今日台股資料未進來，三層備援都沒補到"


def is_trading_day(d) -> bool:
    if d.weekday() >= 5:
        return False
    try:
        cal = json.loads((ROOT / "data" / "trading_calendar.json").read_text(encoding="utf-8"))
        y = (cal.get("tw") or {}).get(str(d.year)) or {}
        return d.isoformat() not in (set(y.get("closed") or []) | set(y.get("unscheduled_closed") or []))
    except Exception as e:  # noqa: BLE001 —— 讀不到日曆照平日判斷（多報一次無害，漏報才有害）
        print(f"::warning::trading_calendar 讀取失敗，照平日判斷：{type(e).__name__}: {e}")
        return True


def market_tw_date(layer: str) -> str | None:
    """雲端讀 checkout 的檔；本機先 fetch 再讀 origin/main 版（本機工作目錄可能落後雲端剛推上去的版本）。"""
    if layer == "local":
        try:
            subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=ROOT, timeout=120, capture_output=True)
            r = subprocess.run(["git", "show", "origin/main:data/market_tw.json"], cwd=ROOT, timeout=60, capture_output=True)
            if r.returncode == 0:
                return json.loads(r.stdout.decode("utf-8")).get("data_date")
        except Exception as e:  # noqa: BLE001
            print(f"::warning::讀 origin/main market_tw 失敗，改讀工作目錄：{type(e).__name__}: {e}")
    return json.loads((ROOT / "data" / "market_tw.json").read_text(encoding="utf-8")).get("data_date")


def decide(now: datetime, data_date: str | None) -> tuple[bool, str]:
    today = now.date()
    if (now.hour, now.minute) < CHECK_HM:
        return False, f"未到 {CHECK_HM[0]}:{CHECK_HM[1]:02d}"
    if not is_trading_day(today):
        return False, f"{today} 非交易日"
    if data_date == today.isoformat():
        return False, f"market_tw 已落地（data_date={data_date}）"
    return True, f"{MESSAGE}（market_tw data_date={data_date}，今天 {today}）"


def write_alarm(now: datetime, alarm: bool, why: str, data_date: str | None, layer: str) -> bool:
    """回傳是否真的改了檔。"""
    old = {}
    try:
        old = json.loads(ALARM_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    today = now.date().isoformat()
    if not alarm and not (old.get("date") == today and old.get("alarm")):
        return False
    doc = {"date": today, "alarm": alarm, "message": MESSAGE if alarm else "", "reason": why,
           "market_tw_data_date": data_date, "checked_at": now.isoformat(timespec="seconds"), "layer": layer,
           "note": "先.一一三-A3：交易日 20:30 後 market_tw 不是今天才告警；App 另以 market_tw＋交易日曆自行判斷"}
    if old.get("date") == today and old.get("alarm") == alarm and old.get("market_tw_data_date") == data_date:
        return False
    ALARM_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def local_push_and_dispatch(alarm: bool) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import local_git_commit as G  # noqa: PLC0415
    print(G.commit_paths(["data/tw_data_alarm.json"], "台股當日資料檢查（先.一一三-A3）：" + ("告警" if alarm else "解除")))
    if alarm:
        r = subprocess.run(["gh", "workflow", "run", "tw_data_landed_check.yml", "-f", "reason=local_20_30"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        print("已叫雲端檢查（失敗推播）" if r.returncode == 0 else f"::warning::叫雲端檢查失敗：{r.stderr.strip()[:200]}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=("cloud", "local"), default="cloud")
    ap.add_argument("--now", default=None)
    a = ap.parse_args(argv)
    try:
        now = datetime.fromisoformat(a.now).astimezone(TW) if a.now else datetime.now(TW)
        data_date = market_tw_date(a.layer)
        alarm, why = decide(now, data_date)
        print(f"check_tw_data_landed（{a.layer}）：{'告警' if alarm else '正常'}（{why}）")
        changed = write_alarm(now, alarm, why, data_date, a.layer)
        if a.layer == "local" and (changed or alarm):
            local_push_and_dispatch(alarm)
        if alarm and a.layer == "cloud":
            print(f"::error::{MESSAGE}（market_tw data_date={data_date}）")
            return 1
    except Exception as e:  # noqa: BLE001 —— 守門員自己的失敗只能降級成警告（十二節）
        print(f"::warning::check_tw_data_landed 自身失敗（不影響其他流程）：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
