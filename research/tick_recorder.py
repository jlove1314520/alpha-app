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

用法（CLI，給人手動補壓縮或檢查用）：
    python research/tick_recorder.py compact 20260907   # 壓縮指定日期
    python research/tick_recorder.py compact-stale      # 壓縮所有非今日的殘留 jsonl
    python research/tick_recorder.py stat               # 列出目前落地的檔案與大小
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


def _cli() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stat"
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
        print("未知指令 " + cmd + "；可用：compact / compact-stale / stat")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
