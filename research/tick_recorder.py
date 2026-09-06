# -*- coding: utf-8 -*-
"""逐筆 tick 落地本機（2026-09-06 總司令裁示【資料一】.1）。

**為什麼要有這支**
盤中微結構研究（假說 #50 的真實滑價估算）唯一的原料就是逐筆成交。FinMind 免費層
不提供盤中資料，付費源在「取得方式鐵律」下屬待採購；我們手上唯一合法、已授權的
逐筆來源就是 Shioaji 的 tick 串流——而它是**串流**，過去的 tick 一旦沒接住就永遠
拿不回來（`api.ticks()` 盤中每日只有 10 次額度，補不了整天）。所以只能從今天開始
一筆一筆存下來，存滿 20 個交易日才有得研究。

**設計三原則（照總司令指定，順序就是優先級）**

1. **絕不影響即時推送**。tick callback 在 Shioaji 的背景執行緒上跑，那條路徑上
   `push_tick()` 的延遲直接就是使用者手機看到報價的延遲。所以 `record()` 只做一件事：
   在鎖裡把一個 dict append 進 list。不開檔、不格式化 JSON、不碰磁碟。真正的
   序列化與寫檔全部在主迴圈每 60 秒呼叫一次的 `flush()` 裡做。
2. **熱資料不經 git**。落地目錄在 `research/data/ticks/`，`research/data/` 本來就在
   `.gitignore` 裡（見該檔），另外再加一條明確的 `research/data/ticks/` 當作雙保險
   兼文件——這種一天可能好幾百 MB 的東西 commit 進公開 repo 是災難。
3. **收盤壓成一份 parquet**。盤中寫 jsonl 是因為它可以 append、行程被砍也不會壞掉
   一整天的資料（parquet 不能一行一行 append）；但幾百個小 jsonl 檔查詢起來慢又佔
   inode，所以 13:45 收盤時壓成當日單一 parquet 再刪掉 jsonl。

**壓縮的安全順序（刪資料前的自保）**
先寫 `YYYYMMDD.parquet.tmp` → 讀回來核對列數與來源 jsonl 行數一致 → rename 成正式檔
→ 才刪 jsonl。任何一步失敗就保留 jsonl 原封不動並回報原因，寧可留著佔空間，也不要
「壓縮失敗還把原始資料刪了」——那是不可逆的。

**行程被砍怎麼辦**：`compact_stale_days()` 在 daemon 啟動時掃一次，把所有「不是今天」
又還留著 jsonl 的日子補壓縮。所以就算 13:45 那次沒跑到（當機、斷電、被 kill），
隔天開盤啟動時會自動補上，不需要另外排一個排程。

**誠實揭露的限制**
- `bid`/`ask` 不是 tick 自帶的欄位（`TickSTKv1` 沒有五檔），是從 `TickState` 取「該
  代號最近一次 BidAsk 回呼收到的最佳買賣價」。所以它是**成交當下最接近的一檔報價**，
  不是嚴格同一個封包的快照；而且動態訂閱的自選股只訂 Tick 沒訂 BidAsk（訂閱數上限
  考量，見 `shioaji_quotes.py` `MAX_DYNAMIC_SUBSCRIPTIONS`），那些代號的 bid/ask
  會是 null。用這份資料估滑價時必須知道這件事。
- 只記股票與期貨的逐筆成交。指數（`QuoteIdxV1`）不是逐筆成交、沒有量也沒有五檔，
  記了對微結構研究沒有用，刻意不收。
- `simtrade=true` 是**試撮**不是真成交（開盤前與盤中瞬間），研究時必須先濾掉。
  這裡照收不濾，因為濾掉就再也還原不回來了；濾是分析端的事。

**磁碟保護（資料一.3）**：上限 20GB，超過就從**最舊一天**刪，刪之前先印出來並
append 進 `ticks/_disk_guard.jsonl`。三個護欄：今天不刪、不刪到只剩零天、紀錄寫在
刪之前。用掉 80% 就開始示警（還不刪）——真的刪到就已經算失敗了，示警是讓人在
那之前還有時間決定要搬走還是加大上限。

用法（CLI，給人手動補壓縮或檢查用）：
    python research/tick_recorder.py compact 20260907   # 壓縮指定日期
    python research/tick_recorder.py compact-stale      # 壓縮所有非今日的殘留 jsonl
    python research/tick_recorder.py stat               # 列出目前落地的檔案與大小
    python research/tick_recorder.py estimate           # 每日容量估算與撐得了幾天
    python research/tick_recorder.py guard --dry-run    # 看看會刪誰（不真的刪）
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TICKS_ROOT = Path(os.environ.get("ALPHA_TICKS_DIR") or (REPO_ROOT / "research" / "data" / "ticks"))
TW_TZ = timezone(timedelta(hours=8))

# 落地開關。預設開；設 ALPHA_TICK_RECORD=0 可以整個關掉（磁碟滿、或要跑不想留檔的
# 測試時用）。關掉時 record()/flush() 直接 return，不會有任何磁碟動作。
RECORD_ENABLED = os.environ.get("ALPHA_TICK_RECORD", "1") != "0"

# jsonl 每行的欄位順序（也是 parquet 的欄位順序）。ts/close/volume/bid/ask 是總司令
# 指定的五個；後面五個旗標是「限價旗標」的完整落地：
#   chg_type  漲跌註記，Shioaji 定義 1=漲停 2=漲 3=平 4=跌 5=跌停 —— 漲停/跌停就是
#             「限價」狀態，這是總司令那一條的主要對應欄位
#   tick_type 內外盤註記 1=買盤成交 2=賣盤成交 0=無法判定 —— 估滑價要靠它分方向
#   suspend   暫停交易
#   simtrade  試撮（不是真成交，見模組 docstring）
#   intraday_odd 盤中零股
FIELDS = ("ts", "close", "volume", "bid", "ask",
          "chg_type", "tick_type", "suspend", "simtrade", "intraday_odd")


def _day_dir(day: str) -> Path:
    return TICKS_ROOT / day


def _parquet_path(day: str) -> Path:
    return TICKS_ROOT / (day + ".parquet")


def _safe_code(code: str) -> str:
    """代號拿來當檔名，只留安全字元。Shioaji 的股票/期貨代號都是英數，這裡是
    防呆（動態清單來自 App 推送，不該假設它一定乾淨）。"""
    cleaned = "".join(c for c in str(code) if c.isalnum() or c in "._-")[:32]
    return cleaned or "unknown"


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _bool(v):
    return None if v is None else bool(v)


def _int(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class TickRecorder:
    """把逐筆 tick 緩衝在記憶體、每 60 秒 flush 成 jsonl。

    執行緒安全：`record()` 由 Shioaji 背景 callback 執行緒呼叫，`flush()` 由主迴圈
    呼叫，兩邊共用 `_buf`，用一把鎖保護。flush 時先在鎖裡把整個 buffer 換成新的空
    dict（O(1)），再在鎖外慢慢寫檔——這樣寫檔期間 callback 完全不會被擋住。
    """

    def __init__(self, root=None, enabled=None):
        self.root = Path(root) if root is not None else TICKS_ROOT
        self.enabled = RECORD_ENABLED if enabled is None else enabled
        self._lock = threading.Lock()
        self._buf = {}          # (day, code) -> [rec, ...]
        self.dropped = 0        # 因例外沒收進來的筆數（誠實統計，不靜默）
        self.written = 0        # 累計已寫進 jsonl 的筆數
        self._warned = False

    # ── 熱路徑：只 append，不碰磁碟 ────────────────────────────────────────
    def record(self, code, tick, bid=None, ask=None) -> None:
        """從一個 Shioaji tick 物件抽出要存的欄位並排進 buffer。

        任何例外都吞掉只記數——這是在 tick callback 熱路徑上，落地是附加功能，
        絕不能因為它壞掉而影響即時推送（`shioaji_quotes.py` callback 外層雖然也有
        try/except，但那會讓同一筆 tick 後續的 `maybe_write_live_state()` 被跳過）。
        """
        if not self.enabled:
            return
        try:
            dt = getattr(tick, "datetime", None)
            if dt is None:
                return
            rec = {
                "ts": dt.isoformat(),
                "close": _num(getattr(tick, "close", None)),
                "volume": _int(getattr(tick, "volume", None)),
                "bid": _num(bid),
                "ask": _num(ask),
                "chg_type": _int(getattr(tick, "chg_type", None)),
                "tick_type": _int(getattr(tick, "tick_type", None)),
                "suspend": _bool(getattr(tick, "suspend", None)),
                "simtrade": _bool(getattr(tick, "simtrade", None)),
                "intraday_odd": _bool(getattr(tick, "intraday_odd", None)),
            }
            key = (dt.strftime("%Y%m%d"), _safe_code(code))
            with self._lock:
                self._buf.setdefault(key, []).append(rec)
        except Exception:
            self.dropped += 1

    def pending(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._buf.values())

    # ── 冷路徑：主迴圈每 60 秒呼叫一次 ────────────────────────────────────
    def flush(self) -> int:
        """把 buffer 寫進 `research/data/ticks/YYYYMMDD/{code}.jsonl`（append）。

        回傳這次寫了幾筆。寫檔失敗的那一個代號會把資料**放回 buffer**，下次 flush
        再試——磁碟暫時被佔用（防毒掃描、備份）是常見的暫時性失敗，直接丟掉資料
        等於永久損失一段不可重來的 tick。
        """
        if not self.enabled:
            return 0
        with self._lock:
            batch, self._buf = self._buf, {}
        if not batch:
            return 0
        n = 0
        for (day, code), recs in batch.items():
            path = self.root / day / (code + ".jsonl")
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8", newline="\n") as f:
                    for r in recs:
                        f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
                n += len(recs)
            except OSError as e:
                with self._lock:
                    self._buf.setdefault((day, code), []).extend(recs)
                if not self._warned:
                    self._warned = True
                    print("  [tick落地] 寫入失敗（已放回緩衝下次再試，只印一次）"
                          + str(path) + "：" + type(e).__name__ + ": " + str(e), flush=True)
        self.written += n
        return n


# ── 壓縮：一天的 jsonl → 一份 parquet ────────────────────────────────────────
def compact(day: str, delete_jsonl: bool = True) -> dict:
    """把 `ticks/YYYYMMDD/` 底下所有 jsonl 併成 `ticks/YYYYMMDD.parquet`。

    回傳 {"day","codes","rows","bytes","deleted","skipped"}。
    `skipped` 有值代表沒做（沒有目錄、或已經有 parquet），不是錯誤。
    """
    d = _day_dir(day)
    out = _parquet_path(day)
    if not d.is_dir():
        return {"day": day, "skipped": "沒有 jsonl 目錄", "rows": 0, "codes": 0}
    if out.exists():
        return {"day": day, "skipped": out.name + " 已存在，不覆蓋", "rows": 0, "codes": 0}

    import pyarrow as pa
    import pyarrow.parquet as pq

    cols = {"code": []}
    for k in FIELDS:
        cols[k] = []
    src_lines = 0
    bad_lines = 0
    files = sorted(d.glob("*.jsonl"))
    for fp in files:
        code = fp.stem
        for line in fp.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            src_lines += 1
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                # 行程被砍時最後一行可能只寫了一半。跳過並計數，不讓一行壞掉的
                # 資料害整天壓縮失敗（那會讓 jsonl 永遠留著、越積越多）。
                bad_lines += 1
                continue
            cols["code"].append(code)
            for k in FIELDS:
                cols[k].append(r.get(k))

    rows = len(cols["code"])
    if rows == 0:
        return {"day": day, "skipped": str(len(files)) + " 個 jsonl 但 0 筆有效資料",
                "rows": 0, "codes": len(files), "bad_lines": bad_lines}

    schema = pa.schema([
        ("code", pa.string()), ("ts", pa.string()),
        ("close", pa.float64()), ("volume", pa.int64()),
        ("bid", pa.float64()), ("ask", pa.float64()),
        ("chg_type", pa.int64()), ("tick_type", pa.int64()),
        ("suspend", pa.bool_()), ("simtrade", pa.bool_()), ("intraday_odd", pa.bool_()),
    ])
    table = pa.table({name: cols[name] for name in schema.names}, schema=schema)

    tmp = out.with_name(out.name + ".tmp")
    pq.write_table(table, tmp, compression="zstd")
    # 讀回來核對列數——寫出去跟讀得回來是兩回事，刪原始資料前一定要親自確認過。
    back = pq.read_table(tmp)
    if back.num_rows != rows:
        tmp.unlink(missing_ok=True)
        return {"day": day, "rows": 0, "codes": len(files),
                "skipped": "核對失敗（寫入 %d 讀回 %d），jsonl 保留" % (rows, back.num_rows)}
    tmp.replace(out)

    deleted = False
    if delete_jsonl:
        shutil.rmtree(d, ignore_errors=True)
        deleted = not d.exists()
    return {"day": day, "codes": len(files), "rows": rows, "src_lines": src_lines,
            "bad_lines": bad_lines, "bytes": out.stat().st_size, "deleted": deleted}


def compact_stale_days(today=None) -> list:
    """壓縮所有「不是今天」的殘留 jsonl 目錄（daemon 啟動時呼叫，補做漏掉的收盤壓縮）。"""
    today = today or datetime.now(TW_TZ).strftime("%Y%m%d")
    if not TICKS_ROOT.is_dir():
        return []
    out = []
    for d in sorted(TICKS_ROOT.iterdir()):
        if d.is_dir() and len(d.name) == 8 and d.name.isdigit() and d.name != today:
            out.append(compact(d.name))
    return out


def stat() -> dict:
    """目前落地狀況（給 CLI 與磁碟保護用）。"""
    days = {}
    if TICKS_ROOT.is_dir():
        for p in sorted(TICKS_ROOT.iterdir()):
            if p.is_dir() and p.name.isdigit():
                files = list(p.glob("*.jsonl"))
                days.setdefault(p.name, {})["jsonl"] = {
                    "files": len(files), "bytes": sum(f.stat().st_size for f in files)}
            elif p.suffix == ".parquet" and p.stem.isdigit():
                days.setdefault(p.stem, {})["parquet"] = {"bytes": p.stat().st_size}
    total = 0
    for d in days.values():
        for v in d.values():
            total += v.get("bytes", 0)
    return {"root": str(TICKS_ROOT), "days": days, "total_bytes": total}


# ── 磁碟保護（2026-09-06 總司令裁示【資料一】.3）─────────────────────────────
# 「超過 20GB 時從最舊一天開始刪，刪之前回報」。
DISK_LIMIT_BYTES = int(os.environ.get("ALPHA_TICKS_DISK_LIMIT_BYTES") or 20 * 1024 ** 3)
# 用掉幾成就開始示警（還不刪）。有這個是因為「刪除」本身就是失敗——真的刪到就代表
# 已經沒地方放了，示警是讓人在那之前還有時間決定要不要搬走或加大上限。
DISK_WARN_RATIO = 0.8
# 保護動作的落地紀錄。**只放記憶體的統計，服務一重啟就歸零、證明不了任何事**
# （CLAUDE.md 四之二），所以刪了什麼一定要 append-only 寫進檔案。這個檔在
# research/data/ 底下，跟 tick 資料一樣不進 git。
DISK_LOG_PATH = TICKS_ROOT / "_disk_guard.jsonl"

# 一筆 jsonl 實測 169 bytes（見 estimate() docstring）。
BYTES_PER_TICK_JSONL = 169


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024.0
    return str(n)


def _log_event(event: dict) -> None:
    """把保護動作 append 進 JSONL。寫不進去也不能讓呼叫端掛掉，但要印出來。"""
    try:
        DISK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        event = {"at": datetime.now(TW_TZ).isoformat(), **event}
        with DISK_LOG_PATH.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as e:
        print("  [tick磁碟保護] 紀錄寫入失敗（動作照做，但沒留下紀錄）："
              + type(e).__name__ + ": " + str(e), flush=True)


def estimate(days_ahead: int = 250) -> dict:
    """估算每日容量與撐得了幾天。

    **有實測資料就用實測，沒有才用假設**——這是資料原則「禁止靜默記 None」的同一
    精神：估計值要標清楚它是估的還是量的。

    - 已經壓成 parquet 的日子：直接取檔案大小的中位數當「每日實際容量」。
    - 一天都還沒壓過（例如剛上線的今天）：退回用假設值估，並在回傳裡把假設
      原封標出來，不假裝那是量到的。

    假設值的來源與算法（2026-09-07 資料一.1 上線時的估計，**尚未經實盤驗證**，
    09-08 收盤後的 資料一.4 會用實測數字取代）：
      單筆 jsonl 169 bytes（實測 json.dumps 出來的長度，欄位固定所以幾乎不變動）
      × 每檔每日約 20,000 筆（台股逐筆交易，中大型股的粗略量級；2330 這種會多得多，
        冷門股少得多，取中間值）
      × 約 109 個標的（固定 5 檔個股＋4 檔期貨＋動態自選股上限 100）
      ≈ 368MB/日的 jsonl；parquet+zstd 對這種高度重複的欄位通常壓到 1/6～1/10，
      估 ~50MB/日。**這兩個數字都是估的，不要當成事實引用。**
    """
    st = stat()
    sizes = [d["parquet"]["bytes"] for d in st["days"].values() if "parquet" in d]
    if sizes:
        sizes.sort()
        per_day = sizes[len(sizes) // 2]
        basis = f"實測（{len(sizes)} 個已壓縮日的中位數）"
    else:
        per_day = int(BYTES_PER_TICK_JSONL * 20000 * 109 / 7)  # 假設 parquet 壓到 1/7
        basis = ("假設（單筆169B × 每檔每日約20000筆 × 約109個標的 ÷ 壓縮比7），"
                 "**尚未經實盤驗證**，資料一.4 會用實測取代")
    used = st["total_bytes"]
    remain = max(DISK_LIMIT_BYTES - used, 0)
    return {
        "per_day_bytes": per_day, "per_day_human": _human(per_day), "basis": basis,
        "used_bytes": used, "used_human": _human(used),
        "limit_bytes": DISK_LIMIT_BYTES, "limit_human": _human(DISK_LIMIT_BYTES),
        "used_ratio": round(used / DISK_LIMIT_BYTES, 4) if DISK_LIMIT_BYTES else None,
        "days_until_limit": (remain // per_day) if per_day else None,
        "days_on_disk": len(st["days"]),
        "horizon_days": days_ahead,
        "projected_bytes_at_horizon": used + per_day * days_ahead,
        "projected_human_at_horizon": _human(used + per_day * days_ahead),
    }


def disk_guard(limit: int | None = None, dry_run: bool = False) -> dict:
    """超過上限時從**最舊一天**開始刪，刪之前先回報（印出來＋寫進 DISK_LOG_PATH）。

    三個不會被 dry_run 關掉的安全護欄，理由都是「刪掉就回不來」：
    1. **今天絕不刪**。今天的資料還在寫，刪了等於自己砍自己的腳。
    2. **最後一天絕不刪**。真的大到只剩一天還超標，那是上限設太小或資料異常，
       該叫人來看，不是把手上唯一一份資料也刪掉。
    3. **每刪一天前先寫紀錄**，寫的是刪之前的狀態（刪完再寫，萬一中途當掉就查無此事）。

    回傳 {"action": "none"|"warn"|"deleted", ...}。`dry_run=True` 只回報要刪誰、不動手。
    """
    limit = DISK_LIMIT_BYTES if limit is None else limit
    st = stat()
    used = st["total_bytes"]
    today = datetime.now(TW_TZ).strftime("%Y%m%d")

    if used <= limit:
        ratio = (used / limit) if limit else 0
        if ratio >= DISK_WARN_RATIO:
            msg = (f"已用 {_human(used)} / 上限 {_human(limit)}"
                   f"（{ratio:.0%}），逼近上限但尚未刪除任何資料")
            print(f"  [tick磁碟保護] ⚠ {msg}", flush=True)
            _log_event({"action": "warn", "used_bytes": used, "limit_bytes": limit,
                        "days_on_disk": len(st["days"])})
            return {"action": "warn", "used_bytes": used, "limit_bytes": limit, "message": msg}
        return {"action": "none", "used_bytes": used, "limit_bytes": limit,
                "used_ratio": round(ratio, 4)}

    # 超標了。由舊到新排，逐日刪到回到上限以下。
    days = sorted(st["days"].keys())
    deleted, freed = [], 0
    for day in days:
        if used - freed <= limit:
            break
        if day == today:
            continue                      # 護欄 1：今天還在寫，不刪
        if len(days) - len(deleted) <= 1:
            break                         # 護欄 2：不刪到只剩零天
        size = sum(v.get("bytes", 0) for v in st["days"][day].values())
        targets = [_parquet_path(day), _day_dir(day)]
        # 護欄 3：先回報再動手，紀錄寫的是「刪之前」的狀態
        print(f"  [tick磁碟保護] 已用 {_human(used - freed)} 超過上限 {_human(limit)}，"
              f"{'（dry-run，不會真的刪）' if dry_run else ''}刪除最舊一天 {day}"
              f"（{_human(size)}）", flush=True)
        _log_event({"action": "dry_run_would_delete" if dry_run else "delete",
                    "day": day, "freed_bytes": size,
                    "used_bytes_before": used - freed, "limit_bytes": limit,
                    "days_on_disk_before": len(days) - len(deleted)})
        if not dry_run:
            for t in targets:
                try:
                    if t.is_dir():
                        shutil.rmtree(t, ignore_errors=True)
                    elif t.exists():
                        t.unlink()
                except OSError as e:
                    print(f"  [tick磁碟保護] 刪除 {t} 失敗：{type(e).__name__}: {e}", flush=True)
        deleted.append(day)
        freed += size

    return {"action": "deleted" if deleted else "none", "dry_run": dry_run,
            "deleted_days": deleted, "freed_bytes": freed,
            "used_bytes_before": used, "used_bytes_after": used - freed,
            "limit_bytes": limit,
            "still_over_limit": (used - freed) > limit}


def _cli() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stat"
    if cmd == "estimate":
        print(json.dumps(estimate(), ensure_ascii=False, indent=1))
        return 0
    if cmd == "guard":
        dry = "--dry-run" in sys.argv
        print(json.dumps(disk_guard(dry_run=dry), ensure_ascii=False, indent=1))
        return 0
    if cmd == "compact":
        if len(sys.argv) < 3:
            print("用法：python research/tick_recorder.py compact YYYYMMDD")
            return 2
        print(json.dumps(compact(sys.argv[2]), ensure_ascii=False, indent=1))
    elif cmd == "compact-stale":
        res = compact_stale_days()
        print(json.dumps(res, ensure_ascii=False, indent=1) if res else "沒有需要壓縮的殘留 jsonl")
    elif cmd == "stat":
        print(json.dumps(stat(), ensure_ascii=False, indent=1))
    else:
        print("未知指令 " + cmd + "；可用：compact / compact-stale / stat / estimate / guard [--dry-run]")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
