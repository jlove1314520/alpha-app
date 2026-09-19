# -*- coding: utf-8 -*-
"""GitHub PAT 到期日追蹤（2026-09-15 總司令裁示【sparklines解凍】防重演四.2）。

**為什麼要這支**：market.yml 卡了 10 天沒人跟進，根因之一是舊 PAT 過期/
缺 scope 這件事，發生了才被動發現。總司令換上新 PAT 後明確要求：往後
PAT 快到期這件事，也要跟其他「已知阻塞影響使用者可見資料」一樣，變成
機器主動算天數、超過門檻就亮燈，不能再靠人記得——同一個精神見
`check_stale_user_visible_blocks.py`。

**只存日期，不存 token（總司令原話，鐵律，無例外）**：
`data/seed/pipeline_registry.json` 的 `github_pat_expiry.expires_at` 只放
一個 ISO 日期字串。這支腳本用 `gh api` 打一次 GitHub API，從回應表頭
`Github-Authentication-Token-Expiration` 讀到期日——**這個值本來就是
GitHub 自己回傳的中繼資料，不是 token 本身**；`gh api` 呼叫本身從
Windows keyring 取用憑證，token 字串全程不經過這支腳本的任何變數或
輸出，登錄檔與 log 都只會看到日期。

用法：
    python scripts/check_pat_expiry.py            # 只讀登錄檔算剩餘天數、回傳告警
    python scripts/check_pat_expiry.py --refresh   # 額外打一次 gh api 更新登錄檔的到期日
        （PAT 換新之後手動跑一次這個；到期日一次設定後要幾個月才會變，
        沒必要塞進 5 分鐘一輪的連通性自檢，那樣只是白打 API 額度）
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 2026-09-19（總司令裁示【最優先】一.3全repo掃描）：本檔print()裡有⚠
# (U+26A0)，Windows主控台cp950編不出來會讓行程崩潰，見
# `scripts/dev_queue_runner.py`同段說明。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "data" / "seed" / "pipeline_registry.json"
TZ = timezone(timedelta(hours=8))
ALERT_THRESHOLD_DAYS = 14


def _load() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _save(doc: dict) -> None:
    REGISTRY.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def refresh() -> str:
    """打一次 gh api，從回應表頭讀到期日並寫回登錄檔。回傳讀到的日期字串（YYYY-MM-DD）。"""
    p = subprocess.run(
        ["gh", "api", "-i", "user"],
        capture_output=True, timeout=20, text=True, encoding="utf-8", errors="replace",
    )
    if p.returncode != 0:
        raise RuntimeError(f"gh api 執行失敗：{(p.stderr or '').strip()[:200]}")
    expires_at = None
    for line in p.stdout.splitlines():
        if line.lower().startswith("github-authentication-token-expiration:"):
            raw = line.split(":", 1)[1].strip()  # 例："2026-12-14 14:44:15 UTC"
            expires_at = raw.split(" ")[0]
            break
    if not expires_at:
        raise RuntimeError(
            "gh api 回應沒有 Github-Authentication-Token-Expiration 表頭"
            "（可能是 token 類型不支援此表頭，或 gh 版本不同），"
            "無法自動判定到期日，需人工向 GitHub 設定頁查證。"
        )
    doc = _load()
    doc["github_pat_expiry"] = {
        "expires_at": expires_at,
        "recorded_at": datetime.now(TZ).isoformat(),
        "alert_threshold_days": ALERT_THRESHOLD_DAYS,
        "note": "只存日期，不存 token 本身（2026-09-15 總司令裁示，鐵律）。"
                "來源：`gh api -i user` 回應表頭 Github-Authentication-Token-Expiration。"
                "PAT 換新後要手動重跑 `python scripts/check_pat_expiry.py --refresh` 更新這裡"
                "——沒有排程自動打這支，避免白耗 API 額度。",
    }
    _save(doc)
    return expires_at


def get_alerts() -> list[tuple[str, int]]:
    """回傳 [(告警訊息, 剩餘天數), ...]，只有剩餘天數 ≤ 門檻才會有內容。
    登錄檔裡還沒有 `github_pat_expiry`（沒 refresh 過）不算告警，只是還沒開始追蹤，
    不誤報成「已過期」。
    """
    try:
        doc = _load()
    except Exception:
        return []
    info = doc.get("github_pat_expiry")
    if not info or not info.get("expires_at"):
        return []
    try:
        y, m, d = (int(x) for x in info["expires_at"].split("-"))
        expires = datetime(y, m, d, tzinfo=TZ)
    except Exception:
        return []
    remaining = (expires.date() - datetime.now(TZ).date()).days
    threshold = info.get("alert_threshold_days", ALERT_THRESHOLD_DAYS)
    if remaining <= threshold:
        msg = f"GitHub PAT 將於 {info['expires_at']}（剩 {remaining} 天）到期，需在到期前換新並更新 keyring/GCM"
        return [(msg, remaining)]
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="打一次 gh api 更新登錄檔的到期日")
    a = ap.parse_args()
    if a.refresh:
        expires_at = refresh()
        print(f"已更新登錄檔：GitHub PAT 到期日 = {expires_at}")
    alerts = get_alerts()
    if not alerts:
        print("目前沒有 PAT 到期告警")
        return 0
    for msg, _remaining in alerts:
        print(f"⚠ {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
