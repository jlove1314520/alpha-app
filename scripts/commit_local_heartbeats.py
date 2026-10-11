# -*- coding: utf-8 -*-
"""先.八十-11（2026-10-12）：本機監測產出檔的心跳提交。

根因：AlphaConnectivity（每 5 分鐘）與 AlphaTwsePublishProbe（收盤後 13～20 時每 15 分鐘）在本機持續寫
research/external_connectivity.jsonl、research/twse_publish_probe.jsonl，但沒有任何一支排程負責 commit 它們——
過去只是偶爾被別的 commit 順手帶上；2026-10-09 21:25 之後就沒人帶，雲端（audit.yml 的停擺自檢、Cowork 全檢）
讀到的 repo 版本停在那一刻，於是回報「46 小時沒心跳」「47.7 小時沒產出」，實際上兩支工作在本機都正常在跑。

做法：兩支工作的 .ps1 每次跑完呼叫本腳本；距離上次 commit 超過 THROTTLE_MIN 才提交一次（避免每 5 分鐘一個 commit），
只收這兩支工作自己的產出檔。用法：python scripts/commit_local_heartbeats.py connectivity|probe
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import local_git_commit as G  # noqa: E402

THROTTLE_MIN = 60
SETS = {
    "connectivity": (["research/external_connectivity.jsonl", "research/connectivity_check.log"], "對外連通性監測心跳（AlphaConnectivity，每小時提交一次）"),
    "probe": (["research/twse_publish_probe.jsonl", "research/twse_probe.log"], "TWSE 發布時間探測心跳（AlphaTwsePublishProbe）"),
}


def main() -> int:
    key = sys.argv[1] if len(sys.argv) > 1 else ""
    if key not in SETS:
        print("用法：commit_local_heartbeats.py connectivity|probe")
        return 0
    paths, label = SETS[key]
    age = G.last_commit_age_min(paths[0])
    if age is not None and age < THROTTLE_MIN:
        print(f"{key}：上次提交 {age:.0f} 分鐘前，未到 {THROTTLE_MIN} 分鐘，本輪不提交")
        return 0
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    print(f"{key}：" + G.commit_paths(paths, f"{label} {now}"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001 -- 守門員自己的失敗只能降級成警告（十二節）
        print(f"[warn] commit_local_heartbeats 失敗：{type(e).__name__}: {e}")
        sys.exit(0)
