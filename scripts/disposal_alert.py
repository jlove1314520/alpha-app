# -*- coding: utf-8 -*-
"""處置股／注意股提醒推播（2026-10-13 總司令【先.八十二】13）。

自選股或真錢持股被列入處置／注意時推播（Web Push，research/web_push.py；VAPID 私鑰只在本機 .env，本程式不讀）。
資料：data/disposal_flags.json（scripts/build_disposal_flags.py，Shioaji api.punish／notice＋TWSE／TPEx 官方備援，每日 18:30）。
對象：
  自選股＝research/data/user_settings.json 的 watchlist＋watchlists.lists（App 跨裝置同步）＋research/.live_watchlist.json codes
  真錢持股＝自動交易白名單標的（auto_rebalance_bb90.WHITELIST：0050／00646／00697B），只用代號、不讀股數金額
同一筆（類別＋代號＋起始／公告日）只推一次，狀態存 research/data/disposal_alert_state.json（.gitignore）。
由 scripts/run_disposal_flags.ps1 在旗標檔產生後呼叫；自身失敗只記 log，不擋旗標檔發布（十二節）。
用法：python scripts/disposal_alert.py [--dry-run]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TW = timezone(timedelta(hours=8))
FLAGS = ROOT / "data" / "disposal_flags.json"
SETTINGS = ROOT / "research" / "data" / "user_settings.json"
LIVE_WL = ROOT / "research" / ".live_watchlist.json"
STATE = ROOT / "research" / "data" / "disposal_alert_state.json"
LABEL = {"disposal": "處置", "notice": "注意"}


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def watch_codes() -> set[str]:
    out: set[str] = set()
    s = ((_read(SETTINGS) or {}).get("settings") or {})
    out |= {str(c) for c in (s.get("watchlist") or []) if c}
    for codes in ((s.get("watchlists") or {}).get("lists") or {}).values():
        out |= {str(c) for c in (codes or []) if c}
    out |= {str(c) for c in ((_read(LIVE_WL) or {}).get("codes") or []) if c}
    return out


def holding_codes() -> set[str]:
    try:
        import auto_rebalance_bb90 as AB
        return set(AB.WHITELIST)
    except Exception:  # noqa: BLE001
        return {"0050", "00646", "00697B"}


def names() -> dict:
    return {c: (v or {}).get("name") for c, v in (((_read(ROOT / "data" / "company_info.json") or {}).get("companies")) or {}).items()}


def find_hits(flags: dict, watch: set, hold: set) -> list[dict]:
    hits = []
    for kind in ("disposal", "notice"):
        for code, info in (flags.get(kind) or {}).items():
            who = (["真錢持股"] if code in hold else []) + (["自選股"] if code in watch else [])
            if not who:
                continue
            key = f"{kind}:{code}:{info.get('start') or info.get('announced')}"
            hits.append({"key": key, "kind": kind, "code": code, "who": who, "info": info})
    return hits


def message(hits: list[dict], nm: dict) -> tuple[str, str]:
    parts = []
    for h in hits:
        i = h["info"]
        when = f"{i['start'][5:]}～{i['end'][5:]}" if h["kind"] == "disposal" and i.get("start") and i.get("end") else f"{(i.get('announced') or '')[5:]} 公告"
        extra = f"，{i['interval']}撮合" if h["kind"] == "disposal" and i.get("interval") else ""
        parts.append(f"{h['code']} {nm.get(h['code']) or ''}（{'／'.join(h['who'])}）列入{LABEL[h['kind']]}股 {when}{extra}")
    title = "處置股／注意股提醒" + (f"（{len(hits)} 檔）" if len(hits) > 1 else "")
    return title, "；".join(parts)[:400]


def main(dry: bool = False, send=None) -> dict:
    flags = _read(FLAGS) or {}
    watch, hold = watch_codes(), holding_codes()
    state = _read(STATE) or {"sent": {}}
    hits = find_hits(flags, watch, hold)
    new = [h for h in hits if h["key"] not in state["sent"]]
    res = {"ts": datetime.now(TW).isoformat(timespec="seconds"), "watch": len(watch), "hold": len(hold),
           "hits": len(hits), "new": len(new), "codes": [h["code"] for h in new], "pushed": None}
    if new and not dry:
        title, body = message(new, names())
        if send is None:
            import web_push
            send = lambda t, b: web_push.send(t, b, kind="disposal")  # noqa: E731
        r = send(title, body)
        res["pushed"] = r.get("ok", 0)
        if r.get("ok"):
            for h in new:
                state["sent"][h["key"]] = res["ts"]
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            res["push_errors"] = (r.get("errors") or [])[:3]  # 沒送達就不記已推，下一輪再試
    print(json.dumps(res, ensure_ascii=False))
    return res


if __name__ == "__main__":
    try:
        main(dry="--dry-run" in sys.argv)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] disposal_alert 失敗：{type(e).__name__}: {e}")
    sys.exit(0)
