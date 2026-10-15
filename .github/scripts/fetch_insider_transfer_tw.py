# -*- coding: utf-8 -*-
"""內部人持股轉讓事前申報（台股上市＋上櫃）每日前向累積（先.九十四-5d）。

來源：`research/DATA_GAP_PLAN.md` 2.10「#41 內部人持股轉讓」——歷史查詢只在
mopsov（robots.txt 全站 Disallow，不抓），官方 openapi 只給「每日快照、不能帶
日期」，所以**只能從今天起往前累積，不回補歷史**。

**兩個官方端點（2026-10-14 18:0x 台北 curl 實測，各 1 次）**：
- TWSE：`https://openapi.twse.com.tw/v1/opendata/t187ap12_L`
  「上市公司每日內部人持股轉讓事前申報表-持股轉讓日報」。日期欄「出表日期」
  （民國 YYYMMDD），身分欄叫「申報人身分」。實測 3 筆（出表日期 1151013）。
- TPEx：`https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap12_O`
  上櫃對應表。日期欄叫「Date」、代號欄「SecuritiesCompanyCode」、名稱欄
  「CompanyName」、身分欄叫「申請人身分」（跟 TWSE 差一個字）。實測 20 筆。
- 其餘 12 個欄位（姓名、轉讓方式、受讓人、持股、有效轉讓期間……）兩邊同名。
- 兩家 swagger 都沒有公布次數上限（`C:\\alpha\\CLAUDE.md` 外部 API 清單）；
  本腳本每次執行各 1 次請求，共用 `data/rate_limit_state.json` 的來源名
  `twse_openapi`／`tpex_openapi`（同源間隔 ≥3 秒，402/403/428/429 封鎖 2 小時
  不重試）。

**做法**：
1. 兩邊各抓 1 次，檢查回應是 JSON 陣列（openapi 對無效路徑回 200＋HTML，
   不能只看狀態碼）。
2. 欄位統一成同一組英文鍵（只改名、不改值，原始字串照存），加 `market`
   （TWSE／TPEx）與 `report_date`（民國轉西元 YYYYMMDD）。
3. 併入 `data/insider_transfer_tw_history.json`：以「整筆內容」的雜湊去重，
   同一份申報隔天又出現在快照裡不會重複記。舊紀錄一律保留，不設上限。
4. 兩邊都失敗或都沒資料 → 不覆蓋既有檔、照實印原因；失敗原因寫進
   `meta.last_run.errors`（有既有檔時才寫）。

**誠實限制**：
- 這是「事前申報」（打算轉讓），不是「實際成交」；實際轉讓結果另有申報，
  本腳本不處理。
- 快照只有最新一天；哪天排程沒跑，那天的申報就永久缺一天（只能事後從 mopsov
  補，而那裡不抓），`meta.report_dates` 可看出缺哪幾天。
- 「姓名」「受讓人」依 2026-10-14 先.九十五-3 總司令裁示**改存雜湊**（`name_hash`／
  `transferee_hash`，SHA-256 前 16 碼、固定前綴），原文不寫進檔案；只留職稱與身分類別（`role`）。
  雜湊仍可去重、辨識「同一人多次申報」。⚠️ 限制：固定前綴寫在公開程式碼裡，有心人拿候選
  姓名逐一算雜湊仍可比對出來——它防的是「公開 repo 裡可直接搜尋到姓名」，不是加密。
- 2026-10-16 先.一〇三-19 總司令裁示改 **HMAC-SHA256**（前 16 碼），金鑰只放 GitHub Secret
  `INSIDER_HASH_KEY`（由總司令本人建立，CC 不經手），沒有金鑰就無法拿候選姓名比對。
  **沒設金鑰時不寫姓名雜湊（存 null）**，不退回舊的固定前綴算法；`meta.hash_scheme` 標明用的是哪一種。
  10/16 以前的舊紀錄仍是 v1 固定前綴雜湊（無原文可重算），新舊雜湊不互通。

用法：
    python .github/scripts/fetch_insider_transfer_tw.py           # 正式抓取
    python .github/scripts/fetch_insider_transfer_tw.py --dry-run # 抓但不寫檔
自測（不連網）：`python scripts/selftest_insider_transfer_tw.py`
"""
from __future__ import annotations

import hashlib
import hmac
import os
import contextlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 —— 主控台不支援 reconfigure 時照舊輸出，不中斷
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PATH = REPO_ROOT / "data" / "insider_transfer_tw_history.json"

TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap12_L"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap12_O"
HEADERS = {"User-Agent": "AlphaApp-InsiderTransferTW " + (os.environ.get("ALPHA_UA_CONTACT") or "contact@alpha-app-project.example")}

RATE_LIMIT_STATE_PATH = REPO_ROOT / "data" / "rate_limit_state.json"
RATE_LIMIT_MIN_INTERVAL_SEC = 3.0
RATE_LIMIT_BLOCK_SECONDS = 2 * 60 * 60
BLOCK_STATUS = (402, 403, 428, 429)

# 原始欄位 → 統一鍵。TWSE／TPEx 只有日期、代號、名稱、身分四欄名稱不同。
COMMON_FIELDS = {
    "姓名": "name",
    "預定轉讓方式及股數-轉讓方式": "transfer_method",
    "預定轉讓方式及股數-轉讓股數": "transfer_shares_on_market",
    "每日於盤中交易最大得轉讓股數": "max_daily_intraday_shares",
    "受讓人": "transferee",
    "目前持有股數-自有持股": "held_own",
    "目前持有股數-保留運用決定權信託股數": "held_trust",
    "預定轉讓總股數-自有持股": "planned_own",
    "預定轉讓總股數-保留運用決定權信託股數": "planned_trust",
    "預定轉讓後持股-自有持股": "after_own",
    "預定轉讓後持股-保留運用決定權信託股數": "after_trust",
    "有效轉讓期間": "valid_period",
}
MARKET_FIELDS = {
    "TWSE": {"出表日期": "report_date_roc", "公司代號": "code", "公司名稱": "company", "申報人身分": "role"},
    "TPEX": {"Date": "report_date_roc", "SecuritiesCompanyCode": "code", "CompanyName": "company", "申請人身分": "role"},
}
SOURCES = {
    "TWSE": ("twse_openapi", TWSE_URL),
    "TPEX": ("tpex_openapi", TPEX_URL),
}


# ---------- 共用節流（與其他 openapi 腳本同一份 rate_limit_state.json） ----------

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


# ---------- 解析 ----------

def roc_to_compact(roc: str) -> str | None:
    """"1151013" → "20261013"；格式不符回 None（不猜）。"""
    s = (roc or "").strip()
    if len(s) not in (6, 7) or not s.isdigit():
        return None
    return f"{int(s[:-4]) + 1911}{s[-4:]}"


def normalize_rows(rows, market: str) -> tuple[list[dict], list[str]]:
    """原始列 → 統一鍵紀錄。回傳（紀錄, 警告）。欄位缺漏照實記警告，不補值。"""
    if not isinstance(rows, list):
        raise ValueError(f"{market} 回應不是 JSON 陣列（{type(rows).__name__}）")
    mapping = {**MARKET_FIELDS[market], **COMMON_FIELDS}
    out: list[dict] = []
    warns: list[str] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            warns.append(f"{market} 第{i}列不是物件，略過")
            continue
        missing = [k for k in mapping if k not in row]
        if missing:
            warns.append(f"{market} 第{i}列缺欄位 {missing}")
        rec = {"market": market}
        for src_key, dst_key in mapping.items():
            v = row.get(src_key)
            rec[dst_key] = v.strip() if isinstance(v, str) else v
        # 先.九十五-3：姓名、受讓人改雜湊，原文不落地
        for plain, hk in (("name", "name_hash"), ("transferee", "transferee_hash")):
            rec[hk] = person_hash(rec.pop(plain, None))
        rec["report_date"] = roc_to_compact(rec.get("report_date_roc") or "")
        if not rec.get("code"):
            warns.append(f"{market} 第{i}列沒有公司代號，略過")
            continue
        rec["id"] = record_id(rec)
        out.append(rec)
    return out, warns


HASH_PREFIX = "alpha-insider-transfer-v1|"  # 舊版（v1）前綴，只留供辨識舊紀錄，不再用來算新雜湊
HASH_KEY_ENV = "INSIDER_HASH_KEY"


def hash_scheme() -> str:
    """目前會用的雜湊方式：有金鑰＝hmac-sha256-v2；沒金鑰＝none（不寫姓名雜湊）。"""
    return "hmac-sha256-v2" if os.environ.get(HASH_KEY_ENV, "").strip() else "none"


def person_hash(v) -> str | None:
    """姓名／受讓人 → HMAC-SHA256 前 16 碼（先.一〇三-19）；空值或沒設金鑰回 None（照實，不補、不退回 v1）。"""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    key = os.environ.get(HASH_KEY_ENV, "").strip()
    if not key:
        return None
    return hmac.new(key.encode("utf-8"), str(v).strip().encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def record_id(rec: dict) -> str:
    """整筆內容（不含 id 本身）的雜湊，用來去重。"""
    body = {k: rec.get(k) for k in sorted(rec) if k != "id"}
    return hashlib.sha1(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def merge(prior: dict | None, new_records: list[dict]) -> tuple[list[dict], int]:
    """併入既有紀錄；回傳（全部紀錄, 新增筆數）。既有紀錄一律保留。"""
    records = list((prior or {}).get("records") or [])
    seen = {r.get("id") for r in records}
    added = 0
    for r in new_records:
        if r["id"] in seen:
            continue
        records.append(r)
        seen.add(r["id"])
        added += 1
    records.sort(key=lambda r: (r.get("report_date") or "", r.get("market") or "", r.get("code") or "", r.get("id")))
    return records, added


def build_doc(records: list[dict], last_run: dict) -> dict:
    dates: dict[str, list[str]] = {"TWSE": [], "TPEX": []}
    for r in records:
        d = r.get("report_date")
        if d and r.get("market") in dates:
            dates[r["market"]].append(d)
    return {
        "meta": {
            "source": "TWSE openapi t187ap12_L ＋ TPEx openapi mopsfin_t187ap12_O（每日內部人持股轉讓事前申報，官方免金鑰）",
            "urls": {"TWSE": TWSE_URL, "TPEX": TPEX_URL},
            "note": ("只往前累積、不回補歷史（歷史在 mopsov，robots 禁止）；這是事前申報，不是實際成交；"
                     "排程沒跑的那天會永久缺一天，見 report_dates。欄位只改名不改值。"),
            "record_count": len(records),
            # 先.一〇三-19：本次新寫入紀錄的姓名雜湊方式；10/16 以前的舊紀錄是 v1 固定前綴 SHA-256，新舊不互通
            "hash_scheme": hash_scheme(),
            "report_dates": {m: sorted(set(v)) for m, v in dates.items()},
            "last_run": last_run,
        },
        "records": records,
    }


# ---------- 抓取 ----------

def fetch_one(market: str) -> list:
    source, url = SOURCES[market]
    _rate_limit_wait_or_raise(source)
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code in BLOCK_STATUS:
        _rate_limit_record_block(source, r.status_code)
        raise RuntimeError(f"{source} 回 HTTP {r.status_code}，已標記封鎖 2 小時")
    r.raise_for_status()
    try:
        return r.json()
    except ValueError as e:
        raise RuntimeError(f"{source} 回應不是 JSON（可能是 200＋HTML 錯誤頁）：{e}") from e


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    errors: list[str] = []
    warns: list[str] = []
    new_records: list[dict] = []
    counts: dict[str, int | None] = {}
    for market in ("TWSE", "TPEX"):
        try:
            recs, w = normalize_rows(fetch_one(market), market)
            new_records += recs
            warns += w
            counts[market] = len(recs)
        except Exception as e:  # noqa: BLE001 —— 一邊失敗不影響另一邊
            errors.append(f"{market}：{e}")
            counts[market] = None
            print(f"{market} 失敗：{e}")

    prior = None
    try:
        prior = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as e:
        # 既有檔壞掉：不覆蓋（覆蓋會丟掉累積的歷史），直接失敗讓人看見
        print(f"既有 {OUT_PATH.name} 讀不回來（{e}），為免覆蓋累積資料，本次不寫檔")
        return 1

    records, added = merge(prior, new_records)
    last_run = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_counts": counts,
        "added": added,
        "errors": errors,
        "warnings": warns[:20],
    }
    for w in warns[:20]:
        print(f"警告：{w}")
    print(f"本次快照 TWSE {counts.get('TWSE')} 筆、TPEx {counts.get('TPEX')} 筆；新增 {added} 筆；累積 {len(records)} 筆")

    if not new_records and prior is None:
        print("兩邊都沒有資料，且沒有既有檔，不寫檔")
        return 1 if errors else 0
    if dry:
        print("--dry-run：不寫檔")
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(build_doc(records, last_run), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"寫入 {OUT_PATH}")
    return 1 if len(errors) == 2 else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
