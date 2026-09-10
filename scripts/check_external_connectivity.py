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


def publish_task_health(now: datetime, rows: list[dict], stalled: list[str]) -> None:
    """把自檢結果併進 data/audit_report.json 的 local_task_health（總司令指定的位置）。

    刻意用「讀出來、只改這一個 key、再寫回去」而不是整份重寫：
    audit_report.json 的其他內容是每晚的資料稽核產生的，不能被這支蓋掉。
    最壞情況是跟稽核那支同時寫、這次的合併被覆蓋，5 分鐘後下一輪就補回來。
    """
    path = ROOT / "data" / "audit_report.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(doc, dict):
            return
        doc["local_task_health"] = {
            "checked_at": now.isoformat(),
            "registry": "data/seed/pipeline_registry.json",
            "alert": bool(stalled),
            "stalled_count": len(stalled),
            "stalled": stalled,
            "tasks": rows,
            "note": "由 scripts/check_external_connectivity.py 每 5 分鐘更新。"
                    "判定依據是產出檔的修改時間，不是排程器回報的狀態——"
                    "狀態顯示成功但什麼都沒產出正是要抓的情況。",
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

    # 常駐工作停擺自檢：跟對外連通性一起做，因為兩者都是「本機到底還活著嗎」。
    task_rows, task_stalls = check_local_tasks(now)
    publish_task_health(now, task_rows, task_stalls)
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
