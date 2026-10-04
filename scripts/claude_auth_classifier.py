# -*- coding: utf-8 -*-
"""先.十四-一：本機 claude -p launcher 輸出分類器（登入過期／額度用盡／其他）。

供 run-marathon-cycle.ps1／run-dev-queue-cycle.ps1／run-hypothesis-queue-cycle.ps1
三支（唯一會呼叫 `claude -p` 的）launcher 在偵測到 $reason 為 ERROR/TIMEOUT 時呼叫，
用純字串特徵判斷這次失敗是不是登入過期／額度用盡，而不是籠統都算「ERROR」。

純字串比對，不呼叫任何網路/API、不依賴 claude CLI 的結構化錯誤格式（版本更新可能
改變格式，純文字特徵比對更穩定，但也可能漏判——刻意保守：抓不到已知特徵就回
UNKNOWN，不自己瞎猜，呼叫端收到 UNKNOWN 就當作普通 ERROR 處理，不升級成紅色橫幅。
這支自己的任何例外都不得讓呼叫端的 launcher 中斷（CLAUDE.md 十二節「守門員自己
的失敗只能降級成警告」），所以 main() 把所有例外都接住、一律印出合法 JSON。

用法：
  python scripts/claude_auth_classifier.py <path-to-stream-json-or-text-file>
  印出一行 JSON 到 stdout：{"status": "...", "matched": "..."}
  status 值域：OK（沒有已知錯誤特徵）／AUTH_EXPIRED／QUOTA_EXCEEDED／UNKNOWN（讀檔失敗）
"""
from __future__ import annotations

import json
import re
import sys

AUTH_PATTERNS = [
    r"login expired",
    r"/login",
    r"please run [`'\"]?claude login",
    r"not authenticated",
    r"authentication_error",
    r"invalid api key",
    r"oauth token expired",
    r"session expired",
    r"please log ?in",
    r"token has expired",
    r"not (currently )?logged ?in",
]
QUOTA_PATTERNS = [
    r"usage limit",
    r"exceeded your (usage|rate) limit",
    r"quota exceeded",
    r"credit balance is too low",
    r"rate_limit_error",
    r"insufficient_quota",
    r"429 too many requests",
    r"over.{0,10}budget",
    r"max.?budget",
]


def classify_text(text: str) -> dict:
    try:
        low = text.lower()
    except Exception:  # noqa: BLE001
        return {"status": "UNKNOWN", "matched": None}
    for pat in AUTH_PATTERNS:
        m = re.search(pat, low)
        if m:
            return {"status": "AUTH_EXPIRED", "matched": m.group(0)}
    for pat in QUOTA_PATTERNS:
        m = re.search(pat, low)
        if m:
            return {"status": "QUOTA_EXCEEDED", "matched": m.group(0)}
    return {"status": "OK", "matched": None}


def classify_file(path: str) -> dict:
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except Exception as e:  # noqa: BLE001
        return {"status": "UNKNOWN", "matched": None, "read_error": f"{type(e).__name__}: {e}"}
    return classify_text(text)


def main() -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    try:
        if len(sys.argv) < 2:
            print(json.dumps({"status": "UNKNOWN", "matched": None, "error": "no path given"}))
            return 0
        print(json.dumps(classify_file(sys.argv[1]), ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001 -- 分類器自己絕不能讓呼叫端的 launcher 炸掉
        print(json.dumps({"status": "UNKNOWN", "matched": None, "error": f"{type(e).__name__}: {e}"}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
