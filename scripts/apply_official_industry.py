"""company_info.json 產業別改以官方公司基本資料為準（2026-10-13 先.八十一-36）。

**為什麼**：company_info.json 的 industry 原本來自 FinMind TaiwanStockInfo，同一個產業有好幾種寫法
（「其他電子類」／「其他電子業」、「數位雲端類」／「數位雲端」、「金融業」／「金融保險」…），
還有母類「電子工業」、舊分類「化學生技醫療」混在裡面——同產業的股票被拆成兩組，
估值的「同產業百分位」與類股資金流都會算錯。

**官方來源（2026-10-13 查證，四個端點各 1 次請求、同源間隔 ≥3 秒）**：
- 上市：`openapi.twse.com.tw/v1/opendata/t187ap03_L`（公司基本資料，欄位「產業別」＝兩碼代碼）
- 上櫃：`www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O`（`SecuritiesIndustryCode`＝代碼）
- 興櫃：`www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_R`（同上）
- 代碼→名稱：`www.tpex.org.tw/openapi/v1/tpex_index_consti`（上櫃指數成分股，`SecuritiesIndustryCode`
  欄位直接是**中文產業名稱**）；與上櫃公司基本資料用公司代號對起來，得到官方「代碼→名稱」，
  10/13 實測 28 個代碼每個都只對到一個名稱（無歧義）。
- 只有上市才有的代碼（01、08、09、11、12、18、91），TPEx 沒有名稱可對；17 兩邊名稱不同（上櫃「金融業」），統一用上市的「金融保險」；
  名稱用 OFFICIAL_TWSE_ONLY_NAMES（TWSE 類股指數 MI_INDEX 有同名類別：水泥類、玻璃陶瓷類、
  造紙類、橡膠類、汽車類、金融保險類、貿易百貨類；存託憑證為 TWSE 證券別）。
兩家 swagger 都沒有公布次數上限；本腳本一次執行 4 次請求。
2026-11-10 先.一三五-1nb-a（提案甲，[預設放行]）：`audit.yml` 每班叫 `--weekly`，上次套用未滿 6 天就零請求略過，
實際每週約 1 次；改接 `data/rate_limit_state.json` 共用節流（來源名 `twse_openapi`／`tpex_openapi`，同源間隔 ≥3 秒，
402/403/428/429 封鎖 2 小時不重試），節流寫法照 `.github/scripts/fetch_insider_transfer_tw.py`（含跨行程鎖）。

**怎麼套**：官方清單裡有的代號，industry 改成官方代碼對應的名稱，記 industry_source／industry_code；
官方清單沒有的（ETF、ETN、受益證券、已下市…）維持原值（FinMind 只補缺），不猜。
官方清單有、company_info 沒有的代號會補進來（名稱用官方簡稱）。
抓取失敗或任一端點筆數過少 → 不覆蓋（exit 1）。
"""
from __future__ import annotations

import collections
import contextlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
CI_PATH = ROOT / "data" / "company_info.json"
MAP_PATH = ROOT / "research" / "data" / "official_industry_code_map.json"
TW_TZ = timezone(timedelta(hours=8))
RATE_LIMIT_STATE_PATH = ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60
BLOCK_STATUS = (402, 403, 428, 429)
WEEKLY_MIN_AGE_DAYS = 6
META_KEY = "official_industry_2026_10_13"

URL_TWSE = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
URL_TPEX_O = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
URL_TPEX_R = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_R"
URL_TPEX_NAMES = "https://www.tpex.org.tw/openapi/v1/tpex_index_consti"

# 上櫃沒有的上市代碼（TPEx 對不到名稱）。名稱依 TWSE 類股指數同名類別（見檔頭）。
OFFICIAL_TWSE_ONLY_NAMES = {
    "01": "水泥工業", "08": "玻璃陶瓷", "09": "造紙工業", "11": "橡膠工業",
    "12": "汽車工業", "17": "金融保險", "18": "貿易百貨", "91": "存託憑證",
}
MIN_ROWS = {"twse": 800, "tpex_o": 700, "tpex_r": 150, "tpex_names": 700}


# ---------- 共用節流（與其他 openapi 腳本同一份 rate_limit_state.json，照抄 fetch_insider_transfer_tw.py） ----------

RATE_LIMIT_LOCK_PATH = RATE_LIMIT_STATE_PATH.with_name(RATE_LIMIT_STATE_PATH.name + ".lock")


@contextlib.contextmanager
def _rate_limit_lock(timeout: float = 15.0, stale_sec: float = 60.0):
    """修.FinMind計數（2026-10-15）：跨行程檔案鎖（O_CREAT|O_EXCL 建 .lock 檔），保護共用狀態檔的
    「讀→改→寫」，避免兩支行程互相覆寫 calls_by_minute／last_request_at（10/15 08:08 撞 402 時狀態檔只記 1～11 次）。
    超過 stale_sec 的鎖視為前一個行程死掉留下的，直接清掉；等不到鎖或建鎖失敗只印警告、不加鎖照常進行
    （fail open，CLAUDE.md 十二節）。各腳本自成一體複製這段（不跨目錄 import 的既有慣例）。"""
    fd = None
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(str(RATE_LIMIT_LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):
            try:
                if time.time() - RATE_LIMIT_LOCK_PATH.stat().st_mtime > stale_sec:
                    RATE_LIMIT_LOCK_PATH.unlink()
                    continue
            except OSError:
                pass  # 鎖剛好被別人釋放／正在刪，下一圈重試
            if time.time() > deadline:
                print(f"[rate_limit] 警告：{timeout:.0f} 秒等不到 {RATE_LIMIT_LOCK_PATH.name}，本次不加鎖照常進行", file=sys.stderr)
                break
            time.sleep(0.05)
        except Exception as e:  # noqa: BLE001 -- 鎖本身失敗只降級成警告（十二節）
            print(f"[rate_limit] 警告：建鎖失敗（{e!r}），本次不加鎖照常進行", file=sys.stderr)
            break
    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
                RATE_LIMIT_LOCK_PATH.unlink()
            except OSError as e:
                print(f"[rate_limit] 警告：釋放鎖失敗（{e!r}），{stale_sec:.0f} 秒後會被視為過期鎖清掉", file=sys.stderr)


def _load_rate_limit_state() -> dict:
    if RATE_LIMIT_STATE_PATH.exists():
        for _ in range(3):  # 修.FinMind計數：別的行程正在換檔時可能讀到半份，稍等重讀，避免拿空狀態蓋掉全部來源
            try:
                return json.loads(RATE_LIMIT_STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                time.sleep(0.05)
    return {"sources": {}}


def _save_rate_limit_state(state: dict) -> None:
    """修.FinMind計數：先寫暫存檔再 os.replace（原子換檔），別的行程不會讀到寫一半的 JSON；
    Windows 上目標檔被開著時 replace 可能 PermissionError，重試 5 次後退回直接覆寫。"""
    RATE_LIMIT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(state, ensure_ascii=False, indent=2)
    tmp = RATE_LIMIT_STATE_PATH.with_name(f"{RATE_LIMIT_STATE_PATH.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        for _ in range(5):
            try:
                os.replace(tmp, RATE_LIMIT_STATE_PATH)
                return
            except PermissionError:
                time.sleep(0.05)
    except Exception as e:  # noqa: BLE001 -- 原子寫入失敗退回直接覆寫（十二節）
        print(f"[rate_limit] 警告：原子寫入失敗（{e!r}），改直接覆寫", file=sys.stderr)
    try:
        tmp.unlink()
    except OSError:
        pass
    RATE_LIMIT_STATE_PATH.write_text(text, encoding="utf-8")


def _rate_limit_wait_or_raise(source: str) -> None:
    # 修.FinMind計數：鎖內「重讀→判斷→只改自己這個來源→寫回」；間隔不夠就放開鎖去睡，醒來重讀再判斷，
    # 不再拿睡前讀到的舊狀態整份寫回（那會蓋掉別的行程在這段時間寫進去的計數）。
    while True:
        with _rate_limit_lock():
            state = _load_rate_limit_state()
            src = state["sources"].get(source, {})
            now = time.time()
            blocked_until = src.get("blocked_until")
            if blocked_until and now < blocked_until:
                remain_min = round((blocked_until - now) / 60, 1)
                raise RuntimeError(f"{source} 封鎖冷卻中（還剩約{remain_min}分鐘，原因：{src.get('block_reason', '未知')}），不送請求")
            last = src.get("last_request_at")
            wait = (RATE_LIMIT_MIN_INTERVAL_SEC - (now - last)) if last else 0.0
            if wait <= 0:
                src["last_request_at"] = now
                state["sources"][source] = src
                _save_rate_limit_state(state)
                return
        time.sleep(wait)


def _rate_limit_record_block(*args, **kwargs) -> None:
    """修.FinMind計數：在跨行程鎖內做「重讀→標封鎖→寫回」（參數原樣轉給 _rate_limit_record_block_unlocked）。"""
    with _rate_limit_lock():
        _rate_limit_record_block_unlocked(*args, **kwargs)


def _rate_limit_record_block_unlocked(source: str, status_code: int) -> None:
    # 只記狀態碼，不記回應內文（避免把任何回應片段寫進公開 repo）
    state = _load_rate_limit_state()
    src = state["sources"].setdefault(source, {})
    src["blocked_until"] = time.time() + RATE_LIMIT_BLOCK_SECONDS
    src["block_reason"] = f"HTTP {status_code}"
    src["blocked_at"] = datetime.now(timezone.utc).isoformat()
    _save_rate_limit_state(state)


def _get(url: str, source: str) -> list[dict]:
    _rate_limit_wait_or_raise(source)
    r = requests.get(url, timeout=60)
    if r.status_code in BLOCK_STATUS:
        _rate_limit_record_block(source, r.status_code)
        raise RuntimeError(f"{source} 回 HTTP {r.status_code}，已標記封鎖 2 小時、不重試")
    r.raise_for_status()
    j = r.json()  # TWSE 無效路徑回 200＋HTML，這裡會直接拋錯（不會靜默吃進去）
    if not isinstance(j, list):
        raise ValueError(f"{url} 不是 JSON 陣列")
    return j


def fetch_all() -> dict[str, list[dict]]:
    # 同源間隔改由共用節流保證（twse_openapi／tpex_openapi 各自 ≥3 秒）
    out = {"twse": _get(URL_TWSE, "twse_openapi")}
    out["tpex_o"] = _get(URL_TPEX_O, "tpex_openapi")
    out["tpex_r"] = _get(URL_TPEX_R, "tpex_openapi")
    out["tpex_names"] = _get(URL_TPEX_NAMES, "tpex_openapi")
    for k, n in MIN_ROWS.items():
        if len(out[k]) < n:
            raise ValueError(f"{k} 只有 {len(out[k])} 筆（< {n}），疑似被限流或端點異常")
    return out


def _weekly_skip(doc: dict) -> str | None:
    """--weekly：上次套用未滿 WEEKLY_MIN_AGE_DAYS 天就回略過理由（零請求）；讀不到時間就照跑（fail open）。"""
    try:
        applied = datetime.fromisoformat(doc["meta"][META_KEY]["applied_at"])
        if applied.tzinfo is None:
            applied = applied.replace(tzinfo=TW_TZ)
        age = datetime.now(TW_TZ) - applied
        if age < timedelta(days=WEEKLY_MIN_AGE_DAYS):
            return f"上次套用 {applied.isoformat(timespec='minutes')}，距今 {age.total_seconds() / 86400:.1f} 天（< {WEEKLY_MIN_AGE_DAYS} 天）"
    except Exception as e:  # noqa: BLE001 -- 讀不到上次時間就照跑，不擋（十二節）
        print(f"[weekly] 警告：讀不到上次套用時間（{e!r}），照常更新")
    return None


def build_code_map(raw: dict) -> tuple[dict[str, str], dict]:
    name_by_sid = {x.get("SecuritiesCompanyCode"): (x.get("SecuritiesIndustryCode") or "").strip() for x in raw["tpex_names"]}
    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for x in raw["tpex_o"]:
        n = name_by_sid.get(x.get("SecuritiesCompanyCode"))
        c = (x.get("SecuritiesIndustryCode") or "").strip()
        if n and c:
            votes[c][n] += 1
    code_map, conflicts = {}, {}
    for c, v in votes.items():
        code_map[c] = v.most_common(1)[0][0]
        if len(v) > 1:
            conflicts[c] = dict(v)
    for c, n in OFFICIAL_TWSE_ONLY_NAMES.items():
        code_map.setdefault(c, n)
    # 代碼 17：上櫃叫「金融業」、上市類股指數叫「金融保險類」，上市 31 檔為多數 → 統一用「金融保險」
    # （research/precheck_supply_tightness.py 兩種都認）。[自行裁量]
    code_map["17"] = OFFICIAL_TWSE_ONLY_NAMES["17"]
    return dict(sorted(code_map.items())), conflicts


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        doc = json.loads(CI_PATH.read_text(encoding="utf-8"))
        companies = doc["companies"]
    except Exception as e:  # noqa: BLE001
        print(f"[error] 讀不到 {CI_PATH.name}：{e}")
        return 1
    if "--weekly" in argv:
        why = _weekly_skip(doc)
        if why:
            print(f"[weekly] 略過（零請求）：{why}")
            return 0
    try:
        raw = fetch_all()
    except Exception as e:  # noqa: BLE001
        print(f"[error] 官方端點抓取失敗：{type(e).__name__}: {e}；不覆蓋")
        return 1
    code_map, conflicts = build_code_map(raw)

    official: dict[str, tuple[str, str, str]] = {}  # 代號 -> (代碼, 簡稱, 來源)
    for x in raw["twse"]:
        official[str(x.get("公司代號", "")).strip()] = ((x.get("產業別") or "").strip(), (x.get("公司簡稱") or "").strip(), "twse_t187ap03_L")
    for key, src in (("tpex_o", "tpex_t187ap03_O"), ("tpex_r", "tpex_t187ap03_R")):
        for x in raw[key]:
            sid = str(x.get("SecuritiesCompanyCode", "")).strip()
            official.setdefault(sid, ((x.get("SecuritiesIndustryCode") or "").strip(), (x.get("CompanyAbbreviation") or "").strip(), src))
    official.pop("", None)

    # 改前歧義量測：官方清單內的股票，同一官方代碼底下出現幾種寫法、幾檔跟官方名稱不同
    def ambiguity(comp: dict) -> dict:
        spellings: dict[str, set] = collections.defaultdict(set)
        differ = missing = 0
        for sid, (code, _, _) in official.items():
            cur = (comp.get(sid) or {}).get("industry")
            if code not in code_map:
                continue
            if not cur:
                missing += 1
                continue
            spellings[code].add(cur)
            differ += cur != code_map[code]
        multi = {c: sorted(s) for c, s in spellings.items() if len(s) > 1}
        return {"label_differs_from_official": differ, "missing": missing,
                "codes_with_multiple_spellings": len(multi), "extra_spellings": sum(len(s) - 1 for s in multi.values()),
                "examples": dict(list(multi.items())[:6])}

    before = ambiguity(companies)
    counts = collections.Counter()
    unknown_codes = collections.Counter()
    for sid, (code, abbr, src) in official.items():
        name = code_map.get(code)
        if not name:
            unknown_codes[code] += 1
            continue
        row = companies.get(sid)
        if row is None:
            companies[sid] = row = {"name": abbr or None, "industry": None}
            counts["added_company"] += 1
        if row.get("industry") != name:
            counts["changed"] += 1
        row["industry"] = name
        row["industry_code"] = code
        row["industry_source"] = src
        counts[src] += 1
    after = ambiguity(companies)

    stamp = datetime.now(TW_TZ).isoformat(timespec="seconds")
    doc.setdefault("meta", {})[META_KEY] = {
        "applied_at": stamp,
        "sources": [URL_TWSE, URL_TPEX_O, URL_TPEX_R, URL_TPEX_NAMES],
        "note": "官方清單內的上市／上櫃／興櫃公司 industry 改用官方產業別代碼對應名稱；清單外（ETF 等）維持原值。腳本 scripts/apply_official_industry.py。",
        "counts": dict(counts),
        "unknown_codes": dict(unknown_codes),
        "code_name_conflicts": conflicts,
        "ambiguity_before": before,
        "ambiguity_after": after,
    }
    tmp = CI_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CI_PATH)
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_PATH.write_text(json.dumps({"generated_at": stamp, "source": "TPEx tpex_index_consti × mopsfin_t187ap03_O（代號對代號）；上市獨有代碼見 scripts/apply_official_industry.py OFFICIAL_TWSE_ONLY_NAMES",
                                    "code_to_name": code_map, "conflicts": conflicts}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"官方代碼 {len(code_map)} 個（衝突 {len(conflicts)}）；套用 {dict(counts)}；未知代碼 {dict(unknown_codes)}")
    print(f"改前：{json.dumps(before, ensure_ascii=False)}")
    print(f"改後：{json.dumps(after, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
