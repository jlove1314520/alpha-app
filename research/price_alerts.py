"""常備.開發-18：自選股到價與事件推播（本機 alpha_live_server 盤中每分鐘檢查）。

三種觸發（每檔每日最多一則，跨三種合計）：
- pct：今日漲跌幅絕對值 ≥ X%（用常駐行程即時報價的 change_pct）
- above／below：成交價 ≥ 漲到價／≤ 跌到價
- event：明天（下一個週一～週五）有事件（data/events.json：除權息、法說會、股東會等）
  ——只看週末，不含國定假日表（事件日前一天若是連假，會在連假前最後一個平日提醒不到，誠實揭露）。

資料新鮮度：只吃「常駐行程即時」報價（記憶體／熱檔），冷檔（git 追蹤的最後收盤快照）
一律不拿來判斷價格類觸發——拿昨天收盤去推「今天漲 5%」是假訊號。

規則存 research/data/auto_trading/price_alert_rules.json；當日已推紀錄存 price_alert_state.json
（.gitignore 已排除 research/data/）。推播走 web_push.send(kind="price_alert")。

守門員原則（CLAUDE.md 第十二節）：run_once() 永不拋例外，任何失敗只回傳 errors，
不得拖垮 alpha_live_server。本模組沒有任何下單能力。
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path

TW = timezone(timedelta(hours=8))
REPO = Path(__file__).resolve().parent.parent
EVENTS_PATH = REPO / "data" / "events.json"
RULES_NAME = "price_alert_rules.json"
STATE_NAME = "price_alert_state.json"
MAX_CODES = 100
MAX_PCT = 20.0
MAX_SEND_ATTEMPTS = 3  # 網路類失敗最多重試 3 分鐘；無訂閱／無金鑰／偏好關閉屬永久性，當日不再試
MARKET_OPEN, MARKET_CLOSE = dtime(9, 0), dtime(13, 30)
CODE_RE = re.compile(r"^[0-9]{4,6}[A-Z]?$")  # 台股代號（含 00697B 這類 ETF）
PERMANENT_ERRORS = ("NO_SUBSCRIPTION", "NO_VAPID_KEY", "PREF_OFF")


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def validate_rules(payload) -> dict:
    """App 送來的規則 → 正規化。格式錯丟 ValueError（端點轉 400）。
    payload: {"rules": {"2330": {"pct": 3, "above": 1200, "below": null, "event": true}, ...}}"""
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(rules, dict):
        raise ValueError("需要 {\"rules\": {代號: {...}}}")
    if len(rules) > MAX_CODES:
        raise ValueError(f"最多 {MAX_CODES} 檔")
    out = {}
    for code, r in rules.items():
        code = str(code).strip().upper()
        if not CODE_RE.match(code):
            raise ValueError(f"代號格式不正確：{code}（目前只支援台股）")
        if not isinstance(r, dict):
            raise ValueError(f"{code} 規則格式不正確")
        n = {"pct": None, "above": None, "below": None, "event": bool(r.get("event"))}
        for k in ("pct", "above", "below"):
            if r.get(k) in (None, ""):
                continue
            v = _num(r.get(k))
            if v is None or v <= 0:
                raise ValueError(f"{code} 的 {k} 必須是正數")
            if k == "pct" and v > MAX_PCT:
                raise ValueError(f"{code} 漲跌幅門檻不得超過 {MAX_PCT}%（台股漲跌停 10%）")
            n[k] = round(v, 4)
        if n["above"] and n["below"] and n["below"] >= n["above"]:
            raise ValueError(f"{code} 跌到價必須低於漲到價")
        if n["pct"] or n["above"] or n["below"] or n["event"]:
            out[code] = n
    return out


def _read_json(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(p: Path, doc: dict) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def load_rules(base: Path) -> dict:
    d = _read_json(Path(base) / RULES_NAME)
    try:
        return validate_rules(d) if isinstance(d, dict) else {}
    except ValueError:
        return {}


def save_rules(base: Path, payload) -> dict:
    rules = validate_rules(payload)
    _write_json(Path(base) / RULES_NAME, {"updated_at": datetime.now(TW).isoformat(timespec="seconds"),
                                          "rules": rules})
    return rules


def load_state(base: Path, today: date) -> dict:
    """當日已推紀錄；日期不是今天就歸零（每檔每日最多一則）。"""
    d = _read_json(Path(base) / STATE_NAME)
    if not isinstance(d, dict) or d.get("date") != today.isoformat():
        return {"date": today.isoformat(), "fired": {}, "attempts": {}, "last_check": None, "last_error": None}
    d.setdefault("fired", {})
    d.setdefault("attempts", {})
    return d


def in_market_hours(now: datetime) -> bool:
    now = now.astimezone(TW)
    return now.weekday() < 5 and MARKET_OPEN <= now.time() <= MARKET_CLOSE


def next_weekday(d: date) -> date:
    n = d + timedelta(days=1)
    while n.weekday() >= 5:
        n += timedelta(days=1)
    return n


def load_events(path: Path = EVENTS_PATH) -> list:
    d = _read_json(path)
    ev = d.get("events") if isinstance(d, dict) else None
    return [e for e in (ev or []) if isinstance(e, dict) and e.get("code") and e.get("date")]


def evaluate(rules: dict, quotes: dict, events: list, today: date, fired: dict) -> list:
    """純函式：回傳要推的 [{code, kind, title, body}]，每檔最多一則，已推過的略過。
    優先序：到價 > 漲跌幅 > 事件（價格類比事件提醒更有時效）。"""
    tomorrow = next_weekday(today).isoformat()
    ev_by_code = {}
    for e in events or []:
        if str(e.get("date")) == tomorrow:
            ev_by_code.setdefault(str(e["code"]), []).append(e)
    out = []
    for code, r in (rules or {}).items():
        if code in (fired or {}):
            continue
        q = (quotes or {}).get(code) or {}
        name = str(q.get("name") or "").strip()
        label = f"{code} {name}".strip()
        last, pct = _num(q.get("last")), _num(q.get("change_pct"))
        hit = None
        if last is not None and last > 0:
            if r.get("above") and last >= r["above"]:
                hit = ("above", f"{label} 漲到 {last:g}", f"已達你設定的漲到價 {r['above']:g}（今日 {pct:+.2f}%）" if pct is not None else f"已達你設定的漲到價 {r['above']:g}")
            elif r.get("below") and last <= r["below"]:
                hit = ("below", f"{label} 跌到 {last:g}", f"已達你設定的跌到價 {r['below']:g}（今日 {pct:+.2f}%）" if pct is not None else f"已達你設定的跌到價 {r['below']:g}")
        if hit is None and r.get("pct") and pct is not None and last is not None and abs(pct) >= r["pct"]:
            hit = ("pct", f"{label} 今日{'上漲' if pct > 0 else '下跌'} {abs(pct):.2f}%", f"超過你設定的 ±{r['pct']:g}%，成交價 {last:g}")
        if hit is None and r.get("event") and ev_by_code.get(code):
            es = ev_by_code[code]
            nm = name or str(es[0].get("name") or "").strip()
            titles = "；".join(f"{e.get('type') or '事件'}：{e.get('title') or ''}".rstrip("：") for e in es[:3])
            hit = ("event", f"{code} {nm} 明天有事件".replace("  ", " "), f"{tomorrow}　{titles}")
        if hit:
            out.append({"code": code, "kind": hit[0], "title": hit[1], "body": hit[2] + "（非投資建議）"})
    return out


def _permanent(res: dict) -> bool:
    return any(str(e).startswith(PERMANENT_ERRORS) for e in res.get("errors", []))


def run_once(base: Path, quotes: dict | None, now: datetime | None = None, events: list | None = None,
             send=None, force_hours: bool = False) -> dict:
    """盤中每分鐘呼叫一次。永不拋例外。quotes 只能傳「常駐行程即時」報價；None＝沒有即時報價（價格類不判斷）。"""
    out = {"ok": True, "checked": False, "sent": [], "errors": []}
    try:
        now = (now or datetime.now(TW)).astimezone(TW)
        if not force_hours and not in_market_hours(now):
            out["reason"] = "非盤中（週一～週五 09:00–13:30）"
            return out
        rules = load_rules(base)
        state = load_state(base, now.date())
        state["last_check"] = now.isoformat(timespec="seconds")
        out["checked"] = True
        out["live_quotes"] = bool(quotes)
        if rules:
            ev = load_events() if events is None else events
            hits = evaluate(rules, quotes or {}, ev, now.date(), state["fired"])
            if send is None:
                import web_push
                send = lambda t, b: web_push.send(t, b, kind="price_alert", base=base)
            for h in hits:
                try:
                    res = send(h["title"], h["body"]) or {}
                except Exception as e:  # noqa: BLE001 — 推播失敗只記錄，不中斷其他檔
                    res = {"ok": 0, "errors": [f"INTERNAL:{type(e).__name__}"]}
                n = state["attempts"].get(h["code"], 0) + 1
                state["attempts"][h["code"]] = n
                if res.get("ok") or _permanent(res) or n >= MAX_SEND_ATTEMPTS:
                    state["fired"][h["code"]] = {"kind": h["kind"], "at": now.isoformat(timespec="seconds"),
                                                 "delivered": int(res.get("ok") or 0)}
                out["sent"].append({"code": h["code"], "kind": h["kind"], "delivered": int(res.get("ok") or 0),
                                    "errors": list(res.get("errors") or [])[:3]})
        state["last_error"] = None
        _write_json(Path(base) / STATE_NAME, state)
    except Exception as e:  # noqa: BLE001 — 守門員自身失敗只降級
        out["ok"] = False
        out["errors"].append(f"{type(e).__name__}: {e}")
    return out


def status(base: Path, now: datetime | None = None) -> dict:
    now = (now or datetime.now(TW)).astimezone(TW)
    st = load_state(base, now.date())
    return {"rules": load_rules(base), "date": st["date"], "fired": st["fired"],
            "last_check": st.get("last_check"), "in_market_hours": in_market_hours(now)}
