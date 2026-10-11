# -*- coding: utf-8 -*-
"""常備.開發-26：系統週報（每週日 20:00 本機排程 AlphaWeeklyReport 產出）。

產出 data/weekly_report.json（repo 追蹤檔、公開），App 日誌頁「系統週報」卡讀取，並送一則 Web Push 摘要。
五個區塊，全部只讀既有檔案，不打任何外部 API、不下單、不切換模式：

  1. system_health  ：data/audit_report.json（稽核閘門、自檢）＋本機排程心跳（STATUS.json local_schedule_heartbeat）
  2. freshness      ：scripts/pipeline_freshness.py 的 evaluate()（跟每 5 分鐘自檢同一套判定）
  3. research       ：research/TRIALS_REGISTRY.jsonl 近 7 日登記與判定分布、PROGRESS_HEARTBEAT 近 7 日心跳
  4. paper          ：data/paper_1b/3/4/7030.json 的累計報酬＋paper_tracking_watch 狀態
  5. live_execution ：data/auto_heartbeat.json（已公開的事件代碼）近 7 日計數

**真錢區塊刻意只放事件代碼計數**：本檔進公開 repo，真錢帳本（數量、均價、金額、損益）只在本機
/auto/ledger（token 必檢）看，這裡不讀帳本、不寫任何金額或股數（同 auto_ledger_view 去識別化原則）。

每個區塊各自 try：單一來源讀不到只在該區塊標 error，不影響其他區塊（CLAUDE.md 第十二節）。
推播失敗只降級成警告。

手動：python scripts/build_weekly_report.py [--no-push] [--now 2026-10-11T20:00:00+08:00]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "research"))
TZ = timezone(timedelta(hours=8))
OUT = ROOT / "data" / "weekly_report.json"
PAPER_FILES = {"paper_1b": "紙上 1b", "paper_3": "紙上 3", "paper_7030": "紙上 70/30"}


def _read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def _parse_ts(v):
    try:
        t = datetime.fromisoformat(str(v))
        return t if t.tzinfo else t.replace(tzinfo=TZ)
    except Exception:
        return None


def _jsonl(p: Path) -> list:
    out = []
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def sec_system_health(now: datetime) -> dict:
    a = _read_json(ROOT / "data" / "audit_report.json")
    sc = a.get("self_check") or {}
    lth = a.get("local_task_health") or {}
    out = {
        "audit_generated_at": a.get("generated_at"),
        "audit_gate_pass": a.get("gate_pass"),
        "violation_rate": a.get("violation_rate"),
        "violation_rate_gate": a.get("violation_rate_gate"),
        "self_check_ok": sc.get("ok"),
        "self_check_failed": [c.get("label") for c in sc.get("checks") or [] if not c.get("ok")],
    }
    ts = _parse_ts(a.get("generated_at"))
    out["audit_age_hours"] = round((now - ts).total_seconds() / 3600, 1) if ts else None
    # 稽核附帶的本機管線告警（含「使用者可見阻塞」「合規」等非新鮮度類告警），只取前 8 條避免灌爆
    out["alerts"] = [str(s)[:160] for s in (lth.get("stalled") or [])][:8]
    out["alerts_total"] = len(lth.get("stalled") or [])
    lvl = "ok"
    if out["audit_gate_pass"] is False or out["self_check_ok"] is False:
        lvl = "bad"
    elif out["alerts_total"] or (out["audit_age_hours"] or 0) > 48:
        lvl = "warn"
    out["level"] = lvl
    return out


def sec_freshness(now: datetime) -> dict:
    import pipeline_freshness as PF
    rows, stalled = PF.evaluate(now)
    c = Counter(r.get("status") for r in rows)
    return {
        "total": len(rows),
        "counts": dict(c),
        "stalled": [{"task": r["task"], "artifact": r["artifact"], "age_min": r.get("age_min"),
                     "missed_shifts": r.get("missed_shifts")}
                    for r in rows if r.get("status") in ("stalled", "missing")],
        "level": "bad" if c.get("stalled", 0) + c.get("missing", 0) >= 3
        else ("warn" if c.get("stalled", 0) + c.get("missing", 0) else "ok"),
    }


def sec_research(now: datetime, since: str) -> dict:
    trials = _jsonl(ROOT / "research" / "TRIALS_REGISTRY.jsonl")
    wk = [t for t in trials if str(t.get("date") or "") >= since]
    verdicts = Counter(str(t.get("verdict") or "未判定").split("（")[0].split("(")[0].strip()[:24] for t in wk)
    hb = [h for h in _jsonl(ROOT / "research" / "PROGRESS_HEARTBEAT.jsonl")
          if (_parse_ts(h.get("ts")) or datetime.min.replace(tzinfo=TZ)) >= now - timedelta(days=7)]
    return {
        "trials_total": len(trials),
        "trials_week": len(wk),
        "verdicts_week": dict(verdicts.most_common(8)),
        "trials_week_names": [str(t.get("name") or "").strip("`")[:60] for t in wk][-10:],
        "heartbeats_week": len(hb),
        "heartbeats_by_track": dict(Counter(h.get("track") or h.get("source") or "其他" for h in hb)),
        "level": "ok",
    }


def sec_paper(now: datetime) -> dict:
    books = []
    for f, label in PAPER_FILES.items():
        try:
            d = _read_json(ROOT / "data" / f"{f}.json")
            books.append({"id": f, "label": label, "as_of": d.get("as_of_date"),
                          "total_return_pct": d.get("total_return_pct")})
        except Exception as e:
            books.append({"id": f, "label": label, "error": f"{type(e).__name__}"})
    try:
        d4 = _read_json(ROOT / "data" / "paper_4.json")
        for k, v in (d4.get("books") or {}).items():
            books.append({"id": f"paper_4:{k}", "label": f"紙上 4 {k}", "as_of": v.get("as_of_date"),
                          "total_return_pct": v.get("total_return_pct"),
                          "bench_0050_return_pct": v.get("bench_0050_return_pct")})
    except Exception as e:
        books.append({"id": "paper_4", "label": "紙上 4", "error": f"{type(e).__name__}"})
    watch = {}
    try:
        w = _read_json(ROOT / "data" / "paper_tracking_watch.json")
        watch = {"status": w.get("status"), "items": len(w.get("items") or []), "generated_at": w.get("generated_at")}
    except Exception as e:
        watch = {"error": type(e).__name__}
    lvl = "warn" if any("error" in b for b in books) or (watch.get("status") not in (None, "OK")) else "ok"
    return {"books": books, "watch": watch, "level": lvl}


def sec_live(now: datetime) -> dict:
    d = _read_json(ROOT / "data" / "auto_heartbeat.json")
    ev = [e for e in d.get("events") or [] if (_parse_ts(e.get("ts")) or datetime.min.replace(tzinfo=TZ))
          >= now - timedelta(days=7)]
    c = Counter(f'{e.get("task")}:{e.get("code")}' for e in ev)
    last = (d.get("events") or [None])[-1]
    hb_ts = _parse_ts(d.get("updated_at"))
    return {
        "events_week": len(ev),
        "codes_week": dict(c),
        "errors_week": sum(1 for e in ev if e.get("code") == "ERROR"),
        "last_event": last,
        "heartbeat_updated_at": d.get("updated_at"),
        "heartbeat_age_hours": round((now - hb_ts).total_seconds() / 3600, 1) if hb_ts else None,
        "note": "只列已公開的排程事件代碼；成交數量、金額、損益只在本機日誌頁（連上電腦）顯示。",
        "level": "bad" if any(e.get("code") == "ERROR" for e in ev) else "ok",
    }


SECTIONS = [("system_health", sec_system_health), ("freshness", sec_freshness),
            ("research", None), ("paper", sec_paper), ("live_execution", sec_live)]


def build(now: datetime) -> dict:
    since = (now - timedelta(days=7)).date().isoformat()
    rep = {"schema": 1, "generated_at": now.isoformat(timespec="seconds"),
           "week_start": since, "week_end": now.date().isoformat(),
           "disclaimer": "研究與紀錄用途，非投資建議"}
    for name, fn in SECTIONS:
        try:
            rep[name] = sec_research(now, since) if name == "research" else fn(now)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 週報區塊 {name} 失敗：{type(e).__name__}: {e}", flush=True)
            rep[name] = {"error": f"{type(e).__name__}: {str(e)[:120]}", "level": "unknown"}
    rep["summary"] = summary_lines(rep)
    return rep


def summary_lines(rep: dict) -> list:
    L = []
    h = rep.get("system_health") or {}
    if "error" not in h:
        L.append(f'系統健康：稽核閘門{"通過" if h.get("audit_gate_pass") else "未通過"}、自檢{"正常" if h.get("self_check_ok") else "異常"}、告警 {h.get("alerts_total", 0)} 條')
    f = rep.get("freshness") or {}
    if "error" not in f:
        n_bad = len(f.get("stalled") or [])
        L.append(f'資料新鮮度：{f.get("total", 0)} 條管線，{n_bad} 條停擺或缺檔')
    r = rep.get("research") or {}
    if "error" not in r:
        L.append(f'研究進度：本週登記試驗 {r.get("trials_week", 0)} 筆（登記檔累計 {r.get("trials_total", 0)} 列），心跳 {r.get("heartbeats_week", 0)} 次')
    p = rep.get("paper") or {}
    if "error" not in p:
        ok = [b for b in p.get("books") or [] if b.get("total_return_pct") is not None]
        L.append(f'紙上追蹤：{len(ok)} 本帳，追蹤看門狗 {(p.get("watch") or {}).get("status") or "未知"}')
    lv = rep.get("live_execution") or {}
    if "error" not in lv:
        L.append(f'真錢執行：本週排程事件 {lv.get("events_week", 0)} 次，錯誤 {lv.get("errors_week", 0)} 次')
    return L


def main() -> int:
    ap = argparse.ArgumentParser(description="系統週報")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--now", default=None)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    now = _parse_ts(a.now) if a.now else datetime.now(TZ)
    rep = build(now)
    out = Path(a.out)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8"))  # 寫檔前驗：壞檔不覆蓋
    tmp.replace(out)
    print("\n".join(rep["summary"]), flush=True)
    if not a.no_push:
        try:
            import web_push
            bad = [k for k, _ in SECTIONS if (rep.get(k) or {}).get("level") in ("bad", "unknown")]
            title = "Alpha 週報" + (f"（{len(bad)} 區需注意）" if bad else "（全部正常）")
            web_push.notify(title, "；".join(rep["summary"])[:220], kind="weekly_report")
        except Exception as e:  # noqa: BLE001
            print(f"[warn] 週報推播失敗：{type(e).__name__}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
