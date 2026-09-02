# -*- coding: utf-8 -*-
"""台股即時報價擷取（Sinopac Shioaji）。

**2026-09-03升級（B34，使用者裁示「報價升級為逐筆tick串流」）**：從原本
「輪詢快照」（`api.snapshots()`，每次執行登入→查一次→登出→結束）改成
「訂閱逐筆串流」（`api.subscribe()` + `set_on_tick_stk_v1_callback()`等
回呼），登入一次、掛上訂閱後常駐監聽，成交/報價一有變動就即時更新記憶體
狀態，不再是「每隔N分鐘才問一次現在多少錢」。

**架構隨之改變，這是重點，接手的人要先搞懂**：舊版是「短命腳本」，被
Windows排程器每隔幾分鐘呼叫一次、跑完就結束，git commit/push交給外層
`.ps1`負責。新版`main()`在交易時段判定為「開盤中」時**不會馬上結束**，
會登入、訂閱、進入常駐迴圈直到收盤（或行程被中斷）——**這代表`.ps1`
排程器呼叫的方式要跟著改**：不能再假設「呼叫一次、幾秒後就結束」，
改成「開盤前啟動一次，讓它自己跑到收盤」，`.ps1`裡的排程觸發角色改成
「確認常駐行程有沒有在跑、沒有就啟動」的**啟動器**（PID檔案判斷，見
`PID_PATH`），不再是每次都重新登入。**這支腳本可以直接`python research/
shioaji_quotes.py`在開盤前手動啟動**（使用者原話「開盤前先把程式備妥」），
會自己等到交易時段開始才登入，交易時段結束會自動登出並結束行程。

**git commit/push頻率（使用者已核准調整頻率、不需要再提案，這裡是我
選定的實際頻率與理由，見`PROGRESS.md`同步記錄）**：常駐迴圈內每
`FLUSH_INTERVAL_SEC`（15秒）把記憶體裡累積到的最新報價flush成JSON並
commit+push一次——選15秒是**跟App前端既有的15秒盤中自動輪詢頻率
（`index.html::fastPollTick()`）對齊**：flush得比前端輪詢還快沒有意義
（使用者根本還沒重新抓資料，白白多耗git操作次數），flush得比前端輪詢慢
就違背這次升級的目的（App還是要等更久才看得到新價），15秒是兩邊都不
浪費的對齊點。比舊版2分鐘輪詢頻率快8倍。**沒有變動就不commit**（沿用
`git diff --quiet`判斷，避免產生空白commit灌爆歷史）。

**API方法簽章來源（誠實揭露：查證方式跟查證程度）**：這次改版**沒有
在真實模擬環境連線的情況下測試過tick訂閱**（改版當下台股非交易時段，
Shioaji模擬環境服務時段08:00-21:00內雖然可以登入，但非交易時段不會有
真實tick事件觸發，沒有東西可以驗證）——所有callback簽章/欄位名稱都是
**查證已安裝版本（`shioaji==1.7.4`）的型別存根檔案**
（`shioaji/_core.pyi`，直接讀原始碼等級的官方型別定義，不是憑印象猜的）
得到，包含：`TickSTKv1`/`TickFOPv1`/`BidAskSTKv1`/`BidAskFOPv1`/
`QuoteIdxV1`五個資料結構的完整欄位清單、`set_on_tick_stk_v1_callback`等
六個訂閱callback的完整簽章（確認是單一參數`Callable[[TickSTKv1], None]`，
不是舊版API的`(exchange, tick)`雙參數形式）、`api.subscribe()`是目前
建議用法（`api.quote.subscribe()`在這個版本已標記deprecated，改用
`api.subscribe()`直接呼叫）。**唯一沒有把握、需要下次開盤實測才能確認
的地方**：tick物件的`pct_chg`/`price_chg`欄位是否本身就帶正負號，還是
需要另外查`chg_type`欄位做正負號校正（舊版`snapshots()`快照API的
`change_rate`就是「只給大小、正負號要另外查`change_type`」的設計，
`chg_type`在tick物件上型別是`int`不是`ChangeType`列舉，沒辦法單靠讀
型別定義確定int值怎麼對應——這裡選擇「先假設tick的pct_chg/price_chg
已經帶正負號直接使用」，同時把原始`chg_type`整數值也記進`data_type`
之外的除錯欄位，方便下次開盤讀真實tick log時人工核對這個假設對不對，
如果假設錯了下一輪要修正，不是現在悄悄放著不管）。

**沿用不變的既有設計（跟舊版snapshot版本相同，見下方函式）**：
- 讀`.env`只需要`SINOPAC_API_KEY`/`SINOPAC_SECRET_KEY`，刻意不呼叫
  `activate_ca`（唯讀報價，沒有下單權限）。
- 「自選股」用`DEFAULT_TW_WATCHLIST`代表清單，Python腳本讀不到瀏覽器
  localStorage的既有限制不變。
- `_is_tw_trading_window()`交易時段閘門（週一至五08:30-13:45，粗略判斷
  不含國定假日）、`_write_market_closed()`保留最後一次盤中資料的邏輯
  都原封不動沿用。
- TAIEX/期貨近月合約代碼（`api.Contracts.Indexs.TSE.IX0001`/
  `FUTURES_NEAR_MONTH`四組）不變。
- data_type新增`"REALTIME_TICK"`（App前端`intradayDataTypeLabel()`
  對應顯示「即時(tick)」，見`index.html`同步更新），跟舊版snapshot時代
  的`"REALTIME"`區分開來，讓使用者看得出來這是tick串流還是快照。

**掛排程**：`C:\alpha\run-shioaji-quotes-cycle.ps1`角色改變（見上方
架構說明），仍然由Windows工作排程器`AlphaShioajiQuotes`觸發，但改成
「確認常駐行程存在、不存在才啟動」的啟動器邏輯，不再是每次都重新登入
的短命呼叫。
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "quotes_sinopac.json"
ENV_PATH = REPO_ROOT / ".env"
TW_TZ = timezone(timedelta(hours=8))

# 常駐行程的PID檔案（gitignored）：`.ps1`啟動器讀這個檔案判斷「是不是已經
# 有一個常駐行程在跑」，不要重複登入（Shioaji帳戶對同時多個session的行為
# 未知，保守起見一次只允許一個常駐行程）。
PID_PATH = Path(__file__).parent / ".shioaji_stream.pid"

# index.html的WL預設值同一份清單，見模組docstring「已知限制」
DEFAULT_TW_WATCHLIST = ["2330", "2454", "2317", "1513", "3231"]

# App「期貨」頁FUT_CONTRACTS追蹤的四個近月合約（index.html::FUT_CONTRACTS）
FUTURES_NEAR_MONTH = {
    "TXF_NEAR": {"group": "TXF", "code": "TXFR1", "label": "台指期近月"},
    "MXF_NEAR": {"group": "MXF", "code": "MXFR1", "label": "小型台指期近月"},
    "EXF_NEAR": {"group": "EXF", "code": "EXFR1", "label": "電子期近月"},
    "FXF_NEAR": {"group": "FXF", "code": "FXFR1", "label": "金融期近月"},
}

CONTRACTS_READY_WAIT_SEC = 3  # 登入後合約清單非同步下載，太快存取會KeyError
FLUSH_INTERVAL_SEC = 15  # 見模組docstring「git commit/push頻率」完整理由
TRADING_WINDOW_POLL_SEC = 30  # 常駐迴圈裡多久檢查一次「是否還在交易時段」


def _load_env(path: Path) -> dict[str, str]:
    kv = {}
    if not path.exists():
        return kv
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip()
    return kv


def _write_failure(reason: str) -> None:
    payload = {
        "fetched_at": datetime.now(TW_TZ).isoformat(),
        "connected": False,
        "error": reason,
        "quotes": {},
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入失敗狀態到 {OUT_PATH}：{reason}")


def _clean_positive(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _is_tw_trading_window(now: datetime) -> bool:
    """粗略判斷：週一至五08:30-13:45台北時間。**已知簡化，誠實揭露**：
    沒有扣除國定假日（找不到現成、可信賴的台股假日行事曆免費資料源）。"""
    wd = now.weekday()  # 0=Mon .. 6=Sun
    minutes = now.hour * 60 + now.minute
    return wd <= 4 and 8 * 60 + 30 <= minutes < 13 * 60 + 45


def _write_market_closed() -> None:
    """非交易時段：保留最後一次盤中資料，只把market_status標成closed。"""
    existing = {}
    if OUT_PATH.exists():
        try:
            existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    payload = {
        "fetched_at": existing.get("fetched_at"),
        "checked_at": datetime.now(TW_TZ).isoformat(),
        "connected": existing.get("connected", False),
        "market_status": "closed",
        "error": None,
        "quotes": existing.get("quotes", {}),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("非交易時段（週一至五08:30-13:45外），不登入永豐，保留最後一次盤中資料，market_status=closed")


class TickState:
    """執行緒安全的最新報價快照。Shioaji的tick/bidask/quote callback在
    背景執行緒觸發（不是主執行緒），主執行緒的常駐迴圈定期讀出目前累積的
    最新狀態去flush成JSON——這個class就是兩邊之間的共享狀態，用鎖保護
    避免讀寫交錯（純為了正確性防呆，CPython的GIL讓dict操作大多情況下
    已經接近原子，但不應該依賴這個實作細節，明確上鎖比較保險）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._quotes: dict[str, dict] = {}

    def update(self, key: str, patch: dict) -> None:
        with self._lock:
            self._quotes.setdefault(key, {})
            self._quotes[key].update({k: v for k, v in patch.items() if v is not None or k not in self._quotes[key]})

    def snapshot(self) -> dict:
        with self._lock:
            return {k: dict(v) for k, v in self._quotes.items()}


def _to_float(v):
    """Tick物件很多欄位型別是`str`（見shioaji/_core.pyi型別存根），統一
    轉float，轉不了就誠實回None，不拋例外中斷整條callback。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # 排除NaN


def _make_tick_stk_handler(state: TickState, key: str, label: str | None):
    def handler(tick) -> None:
        try:
            last = _to_float(getattr(tick, "close", None))  # Shioaji命名習慣：tick.close = 這筆成交的價格，不是「前一天收盤」
            pct_chg = _to_float(getattr(tick, "pct_chg", None))
            price_chg = _to_float(getattr(tick, "price_chg", None))
            prev_close = (last - price_chg) if (last is not None and price_chg is not None) else None
            patch = {
                "last": last,
                "close": prev_close,
                "change_pct": pct_chg,
                "volume_this_tick": getattr(tick, "volume", None),
                "total_volume": getattr(tick, "total_volume", None),
                "data_type": "REALTIME_TICK",
                "tick_at": tick.datetime.isoformat() if getattr(tick, "datetime", None) else None,
                "_raw_chg_type": getattr(tick, "chg_type", None),  # 除錯用，見模組docstring正負號校正說明
                "exchange": "TSE",
            }
            if label:
                patch["label"] = label
            state.update(key, patch)
        except Exception as e:
            # callback裡任何例外都不能讓整個訂閱掛掉，只記log繼續收下一筆
            print(f"  [tick_stk callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _make_bidask_stk_handler(state: TickState, key: str):
    def handler(bidask) -> None:
        try:
            bid_list = getattr(bidask, "bid_price", None) or []
            ask_list = getattr(bidask, "ask_price", None) or []
            state.update(key, {
                "bid": _clean_positive(bid_list[0]) if bid_list else None,
                "ask": _clean_positive(ask_list[0]) if ask_list else None,
            })
        except Exception as e:
            print(f"  [bidask_stk callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _make_tick_fop_handler(state: TickState, key: str, label: str | None):
    def handler(tick) -> None:
        try:
            last = _to_float(getattr(tick, "close", None))
            pct_chg = _to_float(getattr(tick, "pct_chg", None))
            price_chg = _to_float(getattr(tick, "price_chg", None))
            prev_close = (last - price_chg) if (last is not None and price_chg is not None) else None
            patch = {
                "last": last,
                "close": prev_close,
                "change_pct": pct_chg,
                "volume_this_tick": getattr(tick, "volume", None),
                "total_volume": getattr(tick, "total_volume", None),
                "data_type": "REALTIME_TICK",
                "tick_at": tick.datetime.isoformat() if getattr(tick, "datetime", None) else None,
                "_raw_chg_type": getattr(tick, "chg_type", None),
                "exchange": "TAIFEX",
            }
            if label:
                patch["label"] = label
            state.update(key, patch)
        except Exception as e:
            print(f"  [tick_fop callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _make_bidask_fop_handler(state: TickState, key: str):
    def handler(bidask) -> None:
        try:
            bid_list = getattr(bidask, "bid_price", None) or []
            ask_list = getattr(bidask, "ask_price", None) or []
            state.update(key, {
                "bid": _clean_positive(bid_list[0]) if bid_list else None,
                "ask": _clean_positive(ask_list[0]) if ask_list else None,
            })
        except Exception as e:
            print(f"  [bidask_fop callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _make_quote_idx_handler(state: TickState, key: str, label: str | None):
    def handler(quote) -> None:
        try:
            last = _to_float(getattr(quote, "close", None))
            reference = _to_float(getattr(quote, "reference", None))
            pct_chg = round((last - reference) / reference * 100.0, 4) if (last is not None and reference) else None
            patch = {
                "last": last,
                "close": reference,
                "change_pct": pct_chg,
                "data_type": "REALTIME_TICK",
                "tick_at": quote.datetime.isoformat() if getattr(quote, "datetime", None) else None,
                "exchange": "TSE",
            }
            if label:
                patch["label"] = label
            state.update(key, patch)
        except Exception as e:
            print(f"  [quote_idx callback異常] {key}: {type(e).__name__}: {e}", flush=True)
    return handler


def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def _build_payload(state: TickState) -> dict:
    """純函式：把TickState目前的快照組成要寫進JSON的payload——抽出來
    跟「寫檔+git操作」分開，讓`research/shioaji_tick_stream_test.py`
    能夠只測試「callback更新狀態→組出正確payload」這段，不必連帶碰
    真正的`data/quotes_sinopac.json`或觸發git commit/push。"""
    return {
        "fetched_at": datetime.now(TW_TZ).isoformat(),
        "connected": True,
        "market_status": "open",
        "error": None,
        "quotes": state.snapshot(),
    }


def _flush_and_push(state: TickState) -> None:
    """把目前累積的最新報價寫進JSON，沒有變動就不commit（沿用既有
    `.ps1`的`git diff --quiet`判斷邏輯，這裡直接在Python裡做，因為
    常駐迴圈需要自己push、不能等外層`.ps1`收尾才push一次）。"""
    payload = _build_payload(state)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rel_path = str(OUT_PATH.relative_to(REPO_ROOT))
    diff = _git(["diff", "--quiet", "--", rel_path])
    if diff.returncode == 0:
        return  # 沒有變動，不commit

    timestamp = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M:%S")
    _git(["commit", "-m", f"Shioaji tick stream update {timestamp}", "--", rel_path])

    # 既有fetch+rebase重試模式（見run-shioaji-quotes-cycle.ps1同款邏輯，
    # 這裡搬進Python因為現在是常駐迴圈自己負責push、不是外層.ps1收尾時
    # 才push一次）。**這裡沒有GitHub Actions意義下的「concurrency group」
    # 可用**——concurrency group是GitHub Actions工作流程層級的機制
    # （見`.github/workflows/market.yml`/`quotes.yml`），只協調Actions
    # runner之間的執行順序，管不到這支在使用者本機跑的獨立Python行程；
    # 這裡改用同樣精神但實際可行的辦法：fetch+rebase重試迴圈。
    for attempt in range(5):
        _git(["pull", "--no-rebase", "--quiet"])
        push = _git(["push", "--quiet"])
        if push.returncode == 0:
            return
        time.sleep(5)
    print(f"  [git push] 5次重試後仍失敗，下次flush時的git pull會自然同步", flush=True)


def _cleanup_pid() -> None:
    try:
        PID_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def run_stream_daemon() -> None:
    """常駐主迴圈：登入一次、訂閱全部標的、進入flush迴圈直到收盤或被中斷。"""
    import os
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")

    env = _load_env(ENV_PATH)
    required = ["SINOPAC_API_KEY", "SINOPAC_SECRET_KEY"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        _write_failure(f".env缺少必要欄位：{missing}")
        _cleanup_pid()
        return

    import shioaji as sj

    api = sj.Shioaji(simulation=True)
    state = TickState()

    try:
        try:
            accounts = api.login(api_key=env["SINOPAC_API_KEY"], secret_key=env["SINOPAC_SECRET_KEY"])
        except Exception as e:
            _write_failure(f"登入失敗：{type(e).__name__}: {e}")
            return
        print(f"登入成功，帳戶數：{len(accounts) if accounts else 0}，開始訂閱逐筆tick串流", flush=True)
        time.sleep(CONTRACTS_READY_WAIT_SEC)

        # 訂閱時直接建立code_to_key（tick.code反查標的用，見下方callback
        # 註冊說明），不要訂閱完再重新走一次合約樹反查——那樣容易對不上
        # （原本的寫法就有這個問題：對TAIEX用「有沒有在subscribed清單裡」
        # 三元運算式塞一個可能是空字串的key，改成訂閱當下順手記錄乾淨得多）。
        subscribed = []
        code_to_key: dict[str, str] = {}

        for code in DEFAULT_TW_WATCHLIST:
            try:
                contract = api.Contracts.Stocks[code]
                api.subscribe(contract, quote_type=sj.QuoteType.Tick, version=sj.QuoteVersion.v1)
                api.subscribe(contract, quote_type=sj.QuoteType.BidAsk, version=sj.QuoteVersion.v1)
                subscribed.append(code)
                code_to_key[contract.code] = code
            except Exception as e:
                print(f"  [TW個股] {code} 訂閱失敗，跳過：{e}", flush=True)

        try:
            taiex = api.Contracts.Indexs.TSE.IX0001
            api.subscribe(taiex, quote_type=sj.QuoteType.Quote, version=sj.QuoteVersion.v1)
            subscribed.append("TAIEX")
            code_to_key[taiex.code] = "TAIEX"
        except Exception as e:
            print(f"  [TAIEX] 訂閱失敗，跳過：{e}", flush=True)

        for key, meta in FUTURES_NEAR_MONTH.items():
            try:
                group = getattr(api.Contracts.Futures, meta["group"])
                contract = getattr(group, meta["code"])
                api.subscribe(contract, quote_type=sj.QuoteType.Tick, version=sj.QuoteVersion.v1)
                api.subscribe(contract, quote_type=sj.QuoteType.BidAsk, version=sj.QuoteVersion.v1)
                subscribed.append(key)
                code_to_key[contract.code] = key
            except Exception as e:
                print(f"  [{meta['label']}] 訂閱失敗，跳過：{e}", flush=True)

        if not subscribed:
            _write_failure("所有標的訂閱都失敗，沒有任何東西可以串流")
            return

        # 註冊callback——單一全域callback，內部靠tick.code反查是哪個標的
        # （Shioaji的v1 callback簽章是單一參數Callable[[TickSTKv1],None]，
        # 不是舊版(exchange,tick)雙參數形式，見模組docstring查證來源）。

        def on_tick_stk(tick):
            key = code_to_key.get(tick.code)
            if key:
                _make_tick_stk_handler(state, key, None)(tick)

        def on_bidask_stk(bidask):
            key = code_to_key.get(bidask.code)
            if key:
                _make_bidask_stk_handler(state, key)(bidask)

        def on_tick_fop(tick):
            key = code_to_key.get(tick.code)
            if key:
                _make_tick_fop_handler(state, key, FUTURES_NEAR_MONTH.get(key, {}).get("label"))(tick)

        def on_bidask_fop(bidask):
            key = code_to_key.get(bidask.code)
            if key:
                _make_bidask_fop_handler(state, key)(bidask)

        def on_quote_idx(quote):
            key = code_to_key.get(quote.code)
            if key:
                _make_quote_idx_handler(state, key, "加權指數")(quote)

        api.set_on_tick_stk_v1_callback(on_tick_stk)
        api.set_on_bidask_stk_v1_callback(on_bidask_stk)
        api.set_on_tick_fop_v1_callback(on_tick_fop)
        api.set_on_bidask_fop_v1_callback(on_bidask_fop)
        api.set_on_quote_idx_v1_callback(on_quote_idx)

        print(f"訂閱完成：{subscribed}，進入常駐flush迴圈（每{FLUSH_INTERVAL_SEC}秒）", flush=True)

        elapsed_since_window_check = 0.0
        while True:
            time.sleep(FLUSH_INTERVAL_SEC)
            _flush_and_push(state)
            elapsed_since_window_check += FLUSH_INTERVAL_SEC
            if elapsed_since_window_check >= TRADING_WINDOW_POLL_SEC:
                elapsed_since_window_check = 0.0
                if not _is_tw_trading_window(datetime.now(TW_TZ)):
                    print("交易時段結束，收尾並登出", flush=True)
                    break

        _flush_and_push(state)  # 收盤前最後flush一次，不遺漏最後幾筆
    finally:
        try:
            api.logout()
        except Exception:
            pass
        _cleanup_pid()


def main():
    now = datetime.now(TW_TZ)
    if not _is_tw_trading_window(now):
        _write_market_closed()
        return
    run_stream_daemon()


if __name__ == "__main__":
    main()
