# -*- coding: utf-8 -*-
"""對外連通性監測（2026-09-08 總司令裁示 6）。

**為什麼需要這支**：Cowork 連續兩次指出同一個缺口——
`alpha_live_server.py` 的 `/health`、冒煙測試、各排程的健康檢查，
**全部只打 127.0.0.1**。伺服器對自己說「我很好」永遠會成功，
但那句話跟「手機連得到嗎」完全無關。

實際後果（2026-09-08）：總司令回報 Funnel 與 IBKR 都連不上，
而這台機器上**沒有任何紀錄**能說明當時對外是通還是不通——
只能事後補查，查到的還是「現在」的狀態，不是「當時」的。

**這支補的就是那個缺口**：每 5 分鐘從**這台機器往外**驗三件事，
連續兩次失敗就告警，並把每次結果落地成 JSONL，
之後任何「那時候到底通不通」的問題都查得到。

三項檢查（總司令指定）：
  (a) 一般網際網路——排除「整台機器斷網」這個最大宗原因
  (b) `tailscale netcheck`——Tailscale 自己的連通性（UDP／DERP）
  (c) IBKR Gateway 埠——API 埠有沒有在聽（**這是最常靜默失效的一項**：
      Gateway 行程活著但卡在登入畫面時，行程檢查會過、埠檢查才會抓到）

**告警門檻是「連續兩次」不是「一次」**：單次失敗很常是暫時性抖動，
每次都叫會變成狼來了，狼來了的告警比沒有告警更糟——會被學會忽略。

用法：
    python scripts/check_external_connectivity.py          # 跑一次
    python scripts/check_external_connectivity.py --quiet  # 只有告警才輸出
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 2026-09-19（總司令裁示【最優先】一.3全repo掃描）：本檔print()裡有
# ⚠/✓/✗(U+26A0/2713/2717)，Windows主控台cp950編不出來會讓行程崩潰，見
# `scripts/dev_queue_runner.py`同段說明——這支自己就是個守門員（連線
# 健檢），守門員自己崩潰尤其符合★三新規則要防的情境，優先修。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "research" / "external_connectivity.jsonl"
STATE = ROOT / "research" / ".external_connectivity_state.json"
TZ = timezone(timedelta(hours=8))

# 2026-09-08 實測踩到：排程跑這支時沒有 PYTHONIOENCODING，Windows 主控台是
# cp950，印 `⚠`（U+26A0）直接 UnicodeEncodeError 整支崩潰。
# **而那行只在「有問題要告警」時才會走到**——等於這支監測器平常好好的，
# 一旦真的偵測到斷線就自己死掉，什麼都告警不了。這是最糟的失效方式。
# 所以在程式裡強制 UTF-8，不依賴呼叫端有沒有設環境變數。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

# 連續失敗幾次才告警。1 會太吵（暫時性抖動很常見），3 又太慢。
ALERT_AFTER = 2
# 保留幾天的紀錄。這是診斷用的流水帳，不需要永久保存。
KEEP_DAYS = 14

TAILSCALE = r"C:\Program Files\Tailscale\tailscale.exe"
# IBKR Gateway 的四個常見 API 埠：4001/4002 是 Gateway 的實盤/模擬，
# 7496/7497 是 TWS 的實盤/模擬。任一個開著就算通。
IBKR_PORTS = (4001, 4002, 7496, 7497)


def check_internet() -> tuple[bool, str]:
    """(a) 一般網際網路。用兩個不同機構的端點，避免單一站台故障誤判成斷網。"""
    targets = [
        ("https://www.gstatic.com/generate_204", 204),
        ("https://1.1.1.1/", None),
    ]
    errs = []
    for url, want in targets:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "alpha-connectivity-check"})
            with urllib.request.urlopen(req, timeout=8) as r:
                if want is None or r.status == want:
                    return True, f"{url} → {r.status}"
                errs.append(f"{url} → {r.status}（預期 {want}）")
        except Exception as e:  # noqa: BLE001
            errs.append(f"{url} → {type(e).__name__}")
    return False, "；".join(errs)


def check_tailscale() -> tuple[bool, str]:
    """(b) tailscale netcheck。看 UDP 與 DERP 是否正常。"""
    exe = TAILSCALE if Path(TAILSCALE).exists() else "tailscale"
    try:
        p = subprocess.run([exe, "netcheck"], capture_output=True, timeout=45,
                           text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return False, "找不到 tailscale 執行檔"
    except subprocess.TimeoutExpired:
        return False, "netcheck 逾時（45 秒）"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    out = (p.stdout or "") + (p.stderr or "")
    # netcheck 會把進度訊息寫到 stderr，所以不能只看 returncode，要看報告內容
    udp_ok = "UDP: true" in out
    portal = "CaptivePortal: true" in out
    derp = ""
    for line in out.splitlines():
        if "Nearest DERP" in line:
            derp = line.strip()
            break
    if portal:
        return False, "偵測到 captive portal（可能連到需要登入的 WiFi）"
    if not udp_ok:
        return False, f"UDP 不通；{derp or '無 DERP 資訊'}"
    return True, derp or "UDP 正常"


def check_ibkr() -> tuple[bool, str]:
    """(c) IBKR Gateway API 埠。

    **只檢查行程存不存在是不夠的**——Gateway 卡在登入畫面時行程活著、
    埠卻沒開，那正是 2026-09-08 實際發生的情況
    （PID 107800 在跑，4001/4002/7496/7497 全關）。
    """
    open_ports = []
    for port in IBKR_PORTS:
        s = socket.socket()
        s.settimeout(2.0)
        try:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                open_ports.append(port)
        except Exception:  # noqa: BLE001
            pass
        finally:
            s.close()
    if open_ports:
        return True, f"API 埠開啟：{open_ports}"
    return False, ("四個 API 埠全部關閉（4001/4002/7496/7497）"
                   "——Gateway 若在跑多半是卡在登入畫面，需人工重登")


def _load_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _trim_log() -> None:
    """只留最近 KEEP_DAYS 天，避免流水帳無限長大。"""
    if not LOG.exists():
        return
    cutoff = (datetime.now(TZ) - timedelta(days=KEEP_DAYS)).isoformat()
    try:
        lines = LOG.read_text(encoding="utf-8").splitlines()
        kept = [ln for ln in lines if ln[:10] >= cutoff[:10] or '"ts"' not in ln]
        # 保守：解析不出日期的行一律保留，寧可多留也不要誤刪診斷資料
        keep = []
        for ln in lines:
            try:
                if json.loads(ln).get("ts", "") >= cutoff:
                    keep.append(ln)
            except Exception:  # noqa: BLE001
                keep.append(ln)
        if len(keep) != len(lines):
            LOG.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"  ! 修剪 log 失敗（{type(e).__name__}），不影響本次檢查")


# ---------------------------------------------------------------------------
# 常駐工作停擺自檢（2026-09-10 總司令指示二.5）
#
# 為什麼加這一段：2026-09-10 重開機後查出三件事，共同點都是
# 「排程狀態顯示成功、實際上什麼都沒產出」，從外面完全看不出來——
#   * AlphaTwsePublishProbe 的觸發器是 2026-09-08 的一次性 TimeTrigger，
#     跑完那天就永久失效，之後兩天一個樣本都沒收，狀態一直是「就緒」。
#   * AlphaDepCheck 每週固定 0x80070002（找不到 python），壞了至少三週。
#   * AlphaData 每天在第一行 print 就 UnicodeEncodeError 崩潰，
#     alpha.db 從 2026-08-21 起就沒再進過任何一筆資料。
# 對外連通性監測解決的是「網路通不通」，但以上三個網路全通、
# 一樣靜默停擺。所以要有一個「產出有沒有在動」的檢查。
#
# 判定方式刻意選最笨但騙不了人的一種：看**產出檔的修改時間**。
# 「狀態=就緒」「LastTaskResult=0」都可以在什麼事都沒做的情況下成立，
# 檔案時間戳不行——沒寫就是沒寫。
#
# 門檻是預期間隔的 3 倍（總司令指定）：容忍單次延遲與一次重試，
# 但連續錯過三個週期就一定是真的停了。
# 監控清單**不寫在這裡**。2026-09-10（停擺四.3）總司令指示：
# 清點表與自檢必須讀同一份設定，否則遲早出現「表上有、自檢沒監控」的漏洞。
# 單一事實來源：data/seed/pipeline_registry.json
# 判定邏輯：scripts/pipeline_freshness.py（清點表 scripts/pipeline_inventory.py
# 呼叫的是同一支）。要新增／調整監控對象，改登錄檔，不要改這裡。
sys.path.insert(0, str(ROOT / "scripts"))


def check_local_tasks(now: datetime) -> tuple[list[dict], list[str]]:
    """比對每條管線產出的新鮮度，回傳 (逐項結果, 停擺告警文字)。

    這支自己絕不能因為檢查失敗而崩潰——它是監測器，
    監測器死掉比被監測的東西死掉更糟（見本檔開頭 cp950 那段教訓）。
    """
    try:
        from pipeline_freshness import evaluate
        return evaluate(now)
    except Exception as e:  # noqa: BLE001
        print(f"  ! 管線新鮮度檢查載入失敗（{type(e).__name__}: {e}），本輪跳過停擺自檢")
        return [], []


def update_pipeline_fault_ledger(rows: list[dict], now: datetime) -> None:
    """2026-09-15（總司令交辦【工廠一】）：把這一輪的停擺/缺檔狀態累積進
    `data/seed/pipeline_registry.json` 每個節點的 fault_history（次數／最近
    時間／型態），目的是用數據回答「哪個節點最脆弱、哪個能拿掉」。
    邊緣觸發計數邏輯在 scripts/pipeline_fault_ledger.py，這裡只負責呼叫並
    吞掉例外——監測器本體不能因為健康帳寫檔失敗而整輪崩潰。
    """
    try:
        from pipeline_fault_ledger import update_fault_history
        new_faults = update_fault_history(rows, now)
        for msg in new_faults:
            print(f"  + 鏈路節點健康帳：新增一筆故障事件 {msg}")
    except Exception as e:  # noqa: BLE001
        print(f"  ! 鏈路節點健康帳更新失敗（{type(e).__name__}: {e}），本輪跳過，不影響停擺自檢本身")


def update_factory_stability(now: datetime) -> None:
    """2026-09-16（總司令交辦【工廠四】）：算 MTBF 與每週 DevQueue 自走阻塞次數，
    寫 data/factory_stability.json（最新快照）與 data/factory_stability_history.jsonl
    （每週一筆的趨勢記錄）。同樣包一層 try/except，監測器本體不能因為這個
    儀表板寫檔失敗而整輪崩潰。
    """
    try:
        from factory_stability import run as run_factory_stability
        run_factory_stability(now)
    except Exception as e:  # noqa: BLE001
        print(f"  ! 工廠穩定性儀表板更新失敗（{type(e).__name__}: {e}），本輪跳過，不影響停擺自檢本身")


def check_stale_user_visible_blocks() -> list[str]:
    """2026-09-15（總司令裁示【防重演】，sparklines凍結事件教訓）：
    PENDING_QUEUE.md 裡標記【使用者可見】的阻塞項，超過3個交易日沒處理
    就當一項停擺告警——「零」條目10天前就誠實記錄過market.yml PAT
    缺workflow scope這件事，但只有文字沒有機制提醒，一停就是10天沒人
    跟進。同樣包一層 try/except，這支監測器不能因為掃描失敗而整輪崩潰。
    """
    try:
        from check_stale_user_visible_blocks import get_alerts
        return [f"【使用者可見】阻塞已{days}個交易日未處理：{text}"
                for text, days in get_alerts()]
    except Exception as e:  # noqa: BLE001
        print(f"  ! 使用者可見阻塞掃描失敗（{type(e).__name__}: {e}），本輪跳過這項自檢")
        return []


def check_pat_expiry_alerts() -> list[str]:
    """2026-09-15（總司令裁示【防重演】之二）：GitHub PAT 剩餘天數 ≤14 天就告警。
    只讀 pipeline_registry.json 的 github_pat_expiry.expires_at 做日期算術，
    **不打 gh api、不碰 token**——到期日是 `python scripts/check_pat_expiry.py
    --refresh` 手動更新的，這裡只是每輪讀那個已存的日期。同樣包一層
    try/except，監測器不能因為這項失敗而整輪崩潰。
    """
    try:
        from check_pat_expiry import get_alerts
        return [msg for msg, _remaining in get_alerts()]
    except Exception as e:  # noqa: BLE001
        print(f"  ! PAT 到期日檢查失敗（{type(e).__name__}: {e}），本輪跳過這項自檢")
        return []


def check_devqueue_format_mismatch_alerts() -> list[str]:
    """2026-09-18（重構.E1）：`dev_queue_runner.py` 偵測到 `PENDING_QUEUE.md` 散文
    裁示跟「- [ ]」機器可讀格式對不上時，會把 `_format_mismatch` 旗標寫進
    `research/data/dev_queue_state.json`，但這個旗標本輪之前只印在
    `dev_queue_cycle.log` 裡，沒人盯著看就等於沒告警——這是矛盾偵測機制
    （見 `dev_queue_runner.py` 2026-09-18 總司令裁示【最優先·修理自走系統】）
    唯一還沒接上 `local_task_health` 亮燈機制的最後一段。仿 `check_pat_expiry_alerts()`
    同一套寫法：委派給 `dev_queue_runner.get_format_mismatch_alerts()`，這裡只包一層
    try/except，監測器不能因為這項失敗而整輪崩潰。
    """
    try:
        from dev_queue_runner import get_format_mismatch_alerts
        return get_format_mismatch_alerts()
    except Exception as e:  # noqa: BLE001
        print(f"  ! DevQueue佇列格式不符旗標檢查失敗（{type(e).__name__}: {e}），本輪跳過這項自檢")
        return []


def check_domain_blocklist_alerts() -> list[str]:
    """2026-09-20（合規.三，總司令裁示【緊急·合規】）：讀`audit_preflight.py`
    寫進`data/audit_report.json`的`domain_blocklist_scan`欄位，把
    `unguarded`（硬寫黑名單網域卻沒`import net_guard`的檔案）轉成
    `local_task_health`告警——這是2026-09-19 mopsov違規事件（新腳本繞過
    舊防呆）後補上的「規則寫在CLAUDE.md/net_guard.py，但有機器在檢查」
    機制。只讀檔案不重新掃描（掃描本身由`audit_preflight.py`在稽核管線
    跑，這裡是每5分鐘的健康檢查，不重複做重的repo-wide掃描）。
    """
    try:
        path = ROOT / "data" / "audit_report.json"
        if not path.exists():
            return []
        doc = json.loads(path.read_text(encoding="utf-8"))
        scan = doc.get("domain_blocklist_scan") or {}
        unguarded = scan.get("unguarded") or []
        if not unguarded:
            return []
        files = sorted({h["file"] for h in unguarded if isinstance(h, dict) and "file" in h})
        return [f"合規.三：{f} 硬寫黑名單網域字串但未import net_guard（見audit_preflight.py）"
                for f in files]
    except Exception as e:  # noqa: BLE001
        print(f"  ! 黑名單網域告警檢查失敗（{type(e).__name__}: {e}），本輪跳過這項自檢")
        return []


def publish_task_health(now: datetime, rows: list[dict], stalled: list[str],
                         conn_alerts: list[tuple[str, int, str]] | None = None) -> None:
    """把自檢結果併進 data/audit_report.json 的 local_task_health（總司令指定的位置）。

    刻意用「讀出來、只改這一個 key、再寫回去」而不是整份重寫：
    audit_report.json 的其他內容是每晚的資料稽核產生的，不能被這支蓋掉。
    最壞情況是跟稽核那支同時寫、這次的合併被覆蓋，5 分鐘後下一輪就補回來。

    **2026-09-15（總司令交辦）新增 `conn_alerts`**：修之前這裡只收
    `check_local_tasks()`（產出檔mtime新鮮度）的結果，`main()`另外算出的
    `internet`/`tailscale`/`ibkr_gateway` 連續失敗告警（`fail_streak` >=
    `ALERT_AFTER`）只被印到stdout/log，從沒進過`local_task_health`——
    這正是IBKR Gateway斷線6天才被總司令發現的根因：偵測機制本身其實有跑
    （streak有在累計、alert條件也有觸發），只是沒有接到任何人會主動看的
    地方。現在把這批告警併進`stalled`/`alert`，跟產出檔停擺用同一套亮燈
    機制，不用另外教總司令看第二個地方。
    """
    path = ROOT / "data" / "audit_report.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(doc, dict):
            return
        conn_stall_msgs = [f"{name}: 連續失敗{streak}次（{detail}）" for name, streak, detail in (conn_alerts or [])]
        all_stalled = stalled + conn_stall_msgs
        doc["local_task_health"] = {
            "checked_at": now.isoformat(),
            "registry": "data/seed/pipeline_registry.json",
            "alert": bool(all_stalled),
            "stalled_count": len(all_stalled),
            "stalled": all_stalled,
            "tasks": rows,
            "connectivity_alerts": conn_stall_msgs,
            "note": "由 scripts/check_external_connectivity.py 每 5 分鐘更新。"
                    "產出檔停擺依據修改時間判定；connectivity_alerts 額外納入"
                    "internet/tailscale/ibkr_gateway 這類「行程活著但連不上」的"
                    "連續失敗告警（2026-09-15新增，此前只印在log沒亮燈，"
                    "IBKR斷線6天才被發現就是這個缺口）。",
        }
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"  ! 寫入 local_task_health 失敗（{type(e).__name__}: {e}），不影響本次連通性檢查")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="只有告警才輸出")
    a = ap.parse_args()

    now = datetime.now(TZ)
    checks = {
        "internet": check_internet(),
        "tailscale": check_tailscale(),
        "ibkr_gateway": check_ibkr(),
    }
    state = _load_state()
    alerts = []
    record = {"ts": now.isoformat(), "results": {}}

    for name, (ok, detail) in checks.items():
        streak = 0 if ok else int(state.get(name, 0)) + 1
        state[name] = streak
        record["results"][name] = {"ok": ok, "detail": detail, "fail_streak": streak}
        if streak >= ALERT_AFTER:
            alerts.append((name, streak, detail))

    conn_alerts = list(alerts)  # 這裡先存一份快照：只含internet/tailscale/ibkr_gateway，
    # 不含下面task_stalls——task_stalls已經是publish_task_health()自己的stalled參數，
    # 兩邊都塞會在local_task_health.stalled裡重複列一次。

    # 常駐工作停擺自檢：跟對外連通性一起做，因為兩者都是「本機到底還活著嗎」。
    task_rows, task_stalls = check_local_tasks(now)
    # 2026-09-15【工廠一】：每次自檢亮燈（stalled/missing）就把事件累積進
    # 每個節點的健康帳，長期用來回答「哪個節點最脆弱、哪個能拿掉」。
    update_pipeline_fault_ledger(task_rows, now)
    # 2026-09-16【工廠四】：MTBF與每週人工介入次數儀表板，讀的是上面剛更新的
    # 健康帳，所以要排在 update_pipeline_fault_ledger() 之後。
    update_factory_stability(now)
    # 2026-09-15【防重演】：PENDING_QUEUE.md裡【使用者可見】標記的阻塞項也併進
    # 同一批stalled清單——跟產出檔停擺/連通性告警用同一套亮燈機制，不用另外
    # 教總司令看第三個地方。
    task_stalls = (task_stalls + check_stale_user_visible_blocks() + check_pat_expiry_alerts()
                   + check_devqueue_format_mismatch_alerts() + check_domain_blocklist_alerts())
    publish_task_health(now, task_rows, task_stalls, conn_alerts)
    record["local_tasks"] = {"stalled": task_stalls, "checked": len(task_rows)}
    for msg in task_stalls:
        alerts.append(("local_task_stall", 1, msg))

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    STATE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    _trim_log()

    if alerts:
        print("=" * 66)
        print(f"  ⚠ 對外連通性告警  {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 66)
        for name, streak, detail in alerts:
            print(f"  [{name}] 連續失敗 {streak} 次：{detail}")
        print(f"  紀錄：{LOG.relative_to(ROOT)}")
        return 1

    if not a.quiet:
        print(f"對外連通性 {now.strftime('%H:%M:%S')}：", end="")
        print("、".join(f"{n}{'✓' if ok else '✗'}" for n, (ok, _) in checks.items()))
        for name, (ok, detail) in checks.items():
            print(f"  {'✓' if ok else '✗'} {name}: {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
