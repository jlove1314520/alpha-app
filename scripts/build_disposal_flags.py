"""先.五十一-3（2026-10-08 總司令裁示）處置股／注意股旗標：每日 18:30 產生 data/disposal_flags.json。

資料來源與回退鏈（CLAUDE.md 七、資料原則：主來源→備援，每筆帶 source）：
1. 主來源：Shioaji api.punish()（處置）／api.notice()（注意），各呼叫一次。
   官方「使用限制」頁（sinotrade.github.io/zh/tutor/limit/）的 10 秒 50 次合計清單
   未列這兩個端點；本腳本每日只各呼叫一次，遠低於任何合理上限。
   交易所別用 api.Contracts.Stocks[code].exchange（TSE／OTC）判斷；權證等查不到合約者記 unknown。
2. 上櫃交叉補：Shioaji 回來的上櫃（OTC）最新公布日比上市（TSE）舊超過 1 個交易日
   （或上櫃一筆都沒有），就以櫃買中心 OpenAPI（tpex_disposal_information／
   tpex_trading_warning_information，官方公開資料、未公布次數上限、每日各 1 次）補入
   Shioaji 沒有的上櫃代號，source 標 tpex_openapi。
3. 備援：Shioaji 登入或查詢失敗時，處置改用 TWSE OpenAPI announcement/punish＋TPEx，
   注意改用 TWSE announcement/notice＋TPEx（全部官方公開端點），meta 記失敗原因，不靜默。

安全：Shioaji 連線事件訊息可能含身分證字號（2026-10-07 事件），登入前先掛事件回呼，
只印 event_code，原始 info／event 一律不印不存。本腳本只讀行情資料，不涉任何下單。

寫檔：內容（不含 generated_at）沒變就不覆蓋，避免 launcher 每天空 commit。
全部來源都失敗時不覆蓋舊檔，exit 0 並印原因（舊檔的 generated_at 會讓 App 看得出過舊）。
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "disposal_flags.json"
ENV_PATH = ROOT / ".env"
TW_TZ = timezone(timedelta(hours=8))
TPEX_DISPOSAL_URL = "https://www.tpex.org.tw/openapi/v1/tpex_disposal_information"
TPEX_NOTICE_URL = "https://www.tpex.org.tw/openapi/v1/tpex_trading_warning_information"
TWSE_PUNISH_URL = "https://openapi.twse.com.tw/v1/announcement/punish"
TWSE_NOTICE_URL = "https://openapi.twse.com.tw/v1/announcement/notice"
HTTP_TIMEOUT = 30

sys.path.insert(0, str(ROOT / "scripts"))
try:
    from expected_shift_calendar import is_tw_trading_day as _is_trading_day
except Exception as _e:  # noqa: BLE001 — 行事曆載入失敗只退回「週一到五」，不中斷
    print(f"[警告] 交易日曆載入失敗，退回只扣週末：{type(_e).__name__}", flush=True)

    def _is_trading_day(d: date) -> bool:
        return d.weekday() < 5


def trading_days_between(a: date, b: date) -> int:
    """a 之後到 b（含 b）有幾個交易日；a>=b 回 0。"""
    if a >= b:
        return 0
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if _is_trading_day(d):
            n += 1
    return n


def _roc_to_date(s: str) -> date | None:
    """'1151008'／'115/10/08' → date；解析不了回 None。"""
    s = (s or "").strip()
    m = re.fullmatch(r"(\d{2,3})/?(\d{2})/?(\d{2})", s)
    if not m:
        return None
    try:
        return date(int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _period(s: str) -> tuple[date | None, date | None]:
    parts = re.split(r"[~～]", s or "")
    if len(parts) != 2:
        return None, None
    return _roc_to_date(parts[0]), _roc_to_date(parts[1])


def _short_reason(text: str) -> str:
    """從長篇處置說明抓「處置原因：…」那一句；抓不到就取前 60 字。"""
    t = (text or "").replace("\r", "")
    m = re.search(r"處置原因：([^\n]*?。)", t)
    if m:
        return m.group(1).strip()
    return t.strip().split("\n")[0][:60]


def _iso(d) -> str | None:
    return d.isoformat() if d else None


def _http_json(url: str):
    import requests
    r = requests.get(url, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    body = r.text.strip()
    if not body.startswith("["):  # 已知地雷：無效路徑回 200＋HTML，不能只看狀態碼
        raise ValueError("回應不是 JSON 陣列")
    return json.loads(body)


# ── 主來源：Shioaji ─────────────────────────────────────────────
def fetch_shioaji() -> tuple[dict, dict, dict]:
    """回 (punish_columns, notice_columns, exchange_of)。失敗丟例外由呼叫端記錄。"""
    sys.path.insert(0, str(ROOT / "research"))
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    if not env.get("SINOPAC_API_KEY") or not env.get("SINOPAC_SECRET_KEY"):
        raise RuntimeError(".env 缺少 SINOPAC_API_KEY／SINOPAC_SECRET_KEY")
    import shioaji as sj
    api = sj.Shioaji(simulation=True)

    def _evt(resp_code, event_code, info=None, event=None):
        try:
            print(f"  [Shioaji事件] event_code={int(event_code)}", flush=True)
        except Exception:  # noqa: BLE001
            pass
    api.set_event_callback(_evt)  # 必須在 login 前：預設處理器會印出含身分證的原始訊息
    api.login(api_key=env["SINOPAC_API_KEY"], secret_key=env["SINOPAC_SECRET_KEY"])
    try:
        time.sleep(3)  # 合約清單非同步下載（同 shioaji_quotes.CONTRACTS_READY_WAIT_SEC）
        punish = api.punish().dict()
        notice = api.notice().dict()
        exch = {}
        for c in set(punish.get("code") or []) | set(notice.get("code") or []):
            try:
                k = api.Contracts.Stocks[c]
                exch[c] = str(getattr(k, "exchange", "") or "unknown").split(".")[-1]
            except Exception:  # noqa: BLE001 — 權證等不在股票合約內，記 unknown
                exch[c] = "unknown"
        return punish, notice, exch
    finally:
        try:
            api.logout()
        except Exception as e:  # noqa: BLE001
            print(f"[警告] Shioaji 登出失敗（不影響結果）：{type(e).__name__}", flush=True)


def _rows(cols: dict) -> list[dict]:
    keys = list(cols.keys())
    n = len(cols.get("code") or [])
    return [{k: cols[k][i] for k in keys} for i in range(n)]


def shioaji_to_flags(punish: dict, notice: dict, exch: dict) -> tuple[dict, dict]:
    disp, note = {}, {}
    for r in _rows(punish):
        c = str(r.get("code") or "").strip()
        if not c:
            continue
        disp[c] = {
            "start": _iso(r.get("start_date")), "end": _iso(r.get("end_date")),
            "announced": _iso(r.get("announced_date")),
            "interval": r.get("interval") or None,
            "unit_limit": r.get("unit_limit"), "total_limit": r.get("total_limit"),
            "reason": _short_reason(r.get("description") or ""),
            "exchange": exch.get(c, "unknown"), "source": "shioaji_punish",
        }
    for r in _rows(notice):
        c = str(r.get("code") or "").strip()
        if not c:
            continue
        note[c] = {
            "announced": _iso(r.get("announced_date")), "close": r.get("close"),
            "reason": (r.get("reason") or "").strip()[:160],
            "exchange": exch.get(c, "unknown"), "source": "shioaji_notice",
        }
    return disp, note


# ── 官方公開資料（交叉補／備援）──────────────────────────────────
def tpex_disposal() -> dict:
    out = {}
    for r in _http_json(TPEX_DISPOSAL_URL):
        c = str(r.get("SecuritiesCompanyCode") or "").strip()
        if not c:
            continue
        s, e = _period(r.get("DispositionPeriod") or "")
        cond = r.get("DisposalCondition") or ""
        m = re.search(r"約每(\d+)分鐘", cond)
        out[c] = {"start": _iso(s), "end": _iso(e), "announced": _iso(_roc_to_date(r.get("Date") or "")),
                  "interval": f"{m.group(1)}分鐘" if m else None, "unit_limit": None, "total_limit": None,
                  "reason": (r.get("DispositionReasons") or "").strip()[:160],
                  "exchange": "OTC", "source": "tpex_openapi"}
    return out


def tpex_notice() -> dict:
    out = {}
    for r in _http_json(TPEX_NOTICE_URL):
        c = str(r.get("SecuritiesCompanyCode") or "").strip()
        if not c:
            continue
        try:
            close = float(r.get("ClosePrice"))
        except (TypeError, ValueError):
            close = None
        out[c] = {"announced": _iso(_roc_to_date(r.get("Date") or "")), "close": close,
                  "reason": (r.get("TradingInformation") or "").strip()[:160],
                  "exchange": "OTC", "source": "tpex_openapi"}
    return out


def twse_disposal() -> dict:
    out = {}
    for r in _http_json(TWSE_PUNISH_URL):
        c = str(r.get("Code") or "").strip()
        if not c:
            continue
        s, e = _period(r.get("DispositionPeriod") or "")
        det = r.get("Detail") or ""
        m = re.search(r"約每([二三四五十\d]+)分鐘", det)
        out[c] = {"start": _iso(s), "end": _iso(e), "announced": _iso(_roc_to_date(r.get("Date") or "")),
                  "interval": f"{m.group(1)}分鐘" if m else None, "unit_limit": None, "total_limit": None,
                  "reason": _short_reason(det) or (r.get("ReasonsOfDisposition") or "")[:160],
                  "exchange": "TSE", "source": "twse_openapi"}
    return out


def twse_notice() -> dict:
    out = {}
    for r in _http_json(TWSE_NOTICE_URL):
        c = str(r.get("Code") or "").strip()
        if not c:  # 已知：無資料時回一筆全空白列
            continue
        try:
            close = float(r.get("ClosingPrice"))
        except (TypeError, ValueError):
            close = None
        out[c] = {"announced": _iso(_roc_to_date(r.get("Date") or "")), "close": close,
                  "reason": (r.get("TradingInfoForAttention") or "").strip()[:160],
                  "exchange": "TSE", "source": "twse_openapi"}
    return out


# ── 組裝 ─────────────────────────────────────────────────────────
def _latest(flags: dict, exchange: str) -> date | None:
    ds = [date.fromisoformat(v["announced"]) for v in flags.values()
          if v.get("exchange") == exchange and v.get("announced")]
    return max(ds) if ds else None


def otc_lag(flags: dict) -> tuple[int | None, date | None, date | None]:
    """回 (上櫃落後交易日數, 上市最新, 上櫃最新)；上櫃一筆都沒有時落後數回 None。"""
    tse, otc = _latest(flags, "TSE"), _latest(flags, "OTC")
    if otc is None:
        return None, tse, otc
    if tse is None:
        return 0, tse, otc
    return trading_days_between(otc, tse), tse, otc


def merge_missing(base: dict, extra: dict) -> int:
    n = 0
    for c, v in extra.items():
        if c not in base:
            base[c] = v
            n += 1
    return n


def drop_expired(disp: dict, today: date) -> int:
    gone = [c for c, v in disp.items() if v.get("end") and date.fromisoformat(v["end"]) < today]
    for c in gone:
        del disp[c]
    return len(gone)


def build(now: datetime, sj_fetch=fetch_shioaji, tpex_d=tpex_disposal, tpex_n=tpex_notice,
          twse_d=twse_disposal, twse_n=twse_notice) -> dict | None:
    today = now.date()
    meta = {"generated_at": now.isoformat(timespec="seconds"), "errors": [], "supplemented": {}}
    disp, note = {}, {}
    primary_ok = False
    try:
        p, n, ex = sj_fetch()
        disp, note = shioaji_to_flags(p, n, ex)
        primary_ok = True
        meta["primary"] = "shioaji"
    except Exception as e:  # noqa: BLE001
        meta["errors"].append(f"Shioaji 失敗：{type(e).__name__}: {str(e)[:120]}")
        meta["primary"] = "fallback_official_openapi"

    tpex_cache: dict = {}

    def _tpex(kind):
        if kind not in tpex_cache:
            try:
                tpex_cache[kind] = (tpex_d if kind == "d" else tpex_n)()
            except Exception as e:  # noqa: BLE001
                meta["errors"].append(f"TPEx {'處置' if kind == 'd' else '注意'} 失敗：{type(e).__name__}")
                tpex_cache[kind] = None
        return tpex_cache[kind]

    if not primary_ok:
        for kind, target, twse_fn in (("d", disp, twse_d), ("n", note, twse_n)):
            try:
                merge_missing(target, twse_fn())
            except Exception as e:  # noqa: BLE001
                meta["errors"].append(f"TWSE {'處置' if kind == 'd' else '注意'} 失敗：{type(e).__name__}")
            t = _tpex(kind)
            if t:
                meta["supplemented"][kind] = merge_missing(target, t)
        if not disp and not note and len(meta["errors"]) >= 4:
            return None  # 所有來源都失敗：不覆蓋舊檔
    else:
        for kind, target in (("d", disp), ("n", note)):
            lag, tse, otc = otc_lag(target)
            key = "disposal" if kind == "d" else "notice"
            meta[f"{key}_latest_announced"] = {"TSE": _iso(tse), "OTC": _iso(otc), "otc_lag_trading_days": lag}
            if lag is None or lag > 1:
                t = _tpex(kind)
                meta["supplemented"][key] = merge_missing(target, t) if t else 0
                meta[f"{key}_supplement_reason"] = ("Shioaji 上櫃無資料" if lag is None
                                                     else f"Shioaji 上櫃落後上市 {lag} 個交易日")

    meta["expired_dropped"] = drop_expired(disp, today)
    meta["counts"] = {"disposal": len(disp), "notice": len(note)}
    meta["note"] = ("處置股＝交易所公告分盤撮合（每 N 分鐘撮合一次）與預收款券；注意股＝當日公布注意交易資訊。"
                    "App 個股頁紅標、AI 選股候選排除處置期間內個股。非投資建議。")
    return {"meta": meta, "disposal": dict(sorted(disp.items())), "notice": dict(sorted(note.items()))}


def _strip_volatile(d: dict) -> dict:
    d = json.loads(json.dumps(d, ensure_ascii=False))
    d.get("meta", {}).pop("generated_at", None)
    return d


def main() -> int:
    now = datetime.now(TW_TZ)
    out = build(now)
    if out is None:
        print("[失敗] 所有來源都失敗，不覆蓋舊檔", flush=True)
        return 0
    for e in out["meta"]["errors"]:
        print(f"[警告] {e}", flush=True)
    try:
        old = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        if _strip_volatile(old) == _strip_volatile(out):
            print(f"[不變] 處置 {out['meta']['counts']['disposal']}／注意 {out['meta']['counts']['notice']}，內容未變不覆蓋", flush=True)
            return 0
    except (OSError, ValueError):
        pass
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(OUT_PATH)
    print(f"[寫入] {OUT_PATH.name}：處置 {out['meta']['counts']['disposal']}／注意 {out['meta']['counts']['notice']}，"
          f"主來源={out['meta']['primary']}，交叉補={out['meta']['supplemented']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
