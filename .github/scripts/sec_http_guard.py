# -*- coding: utf-8 -*-
"""SEC 連線狀態記錄（先.一〇三-1b-3，2026-10-16 總司令裁示）。

為什麼要有：先.一〇三-16 把 SEC 腳本的 User-Agent 聯絡信箱改讀 ALPHA_UA_CONTACT（沒設時用專案佔位信箱）。
SEC 官方要求 User-Agent 帶可聯絡的資訊，佔位信箱可能被擋（403）。被擋時各腳本原本只是各自記一筆錯誤、
保留舊檔，總司令看不出「是整批被擋」。

做法：SEC 系列腳本開頭 `import sec_http_guard`（一行），本模組在該行程內包住 requests.get／Session.get，
只記「打到 sec.gov 的回應狀態碼」；行程結束時合併寫進 data/sec_access_status.json。
這一輪有任何 403 → 印 GitHub Actions 黃色警告（::warning::，不讓步驟失敗）；generate_status_json.py 把它
寫進 STATUS.json 的 sec_access：「疑似 User-Agent 被擋，請總司令設 ALPHA_UA_CONTACT」。

十二節：本模組自身任何錯誤只印警告，不影響腳本抓資料。十節：輸出 data/sec_access_status.json 已加進
market.yml、us_financials.yml 的 git add 清單。
"""
from __future__ import annotations

import atexit
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "sec_access_status.json"
TZ = timezone(timedelta(hours=8))
WARNING_TEXT = "疑似 User-Agent 被擋，請總司令設 ALPHA_UA_CONTACT"
SCRIPT = Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "unknown"
_COUNTS: Counter = Counter()


def _note(url, status) -> None:
    try:
        if "sec.gov" in str(url):
            _COUNTS[str(status)] += 1
    except Exception as e:  # noqa: BLE001
        print(f"::warning::sec_http_guard 記錄失敗（不影響抓取）：{type(e).__name__}: {e}")


def _install() -> None:
    try:
        import requests
    except Exception:  # noqa: BLE001 -- 腳本沒用 requests 就什麼都不做
        return
    orig_request = requests.Session.request

    def request(self, method, url, *a, **kw):
        try:
            r = orig_request(self, method, url, *a, **kw)
        except Exception:
            _note(url, "error")
            raise
        _note(url, getattr(r, "status_code", "?"))
        return r

    requests.Session.request = request  # requests.get 內部也走 Session.request


def _flush() -> None:
    if not _COUNTS:
        return
    try:
        now = datetime.now(TZ).isoformat(timespec="seconds")
        doc = {}
        if OUT.exists():
            try:
                doc = json.loads(OUT.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                doc = {}
        scripts = doc.get("scripts") or {}
        prev = scripts.get(SCRIPT) or {}
        n403 = _COUNTS.get("403", 0)
        scripts[SCRIPT] = {
            "last_run_at": now,
            "status_counts": dict(sorted(_COUNTS.items())),
            "last_403_at": now if n403 else prev.get("last_403_at"),
            "last_run_403": bool(n403),
            "ua_contact_set": bool(os.environ.get("ALPHA_UA_CONTACT")),
        }
        blocked = sorted(k for k, v in scripts.items() if v.get("last_run_403"))
        doc = {
            "generated_at": now,
            "note": "SEC（sec.gov／data.sec.gov）各腳本最近一輪的回應狀態碼；最近一輪有 403＝疑似 User-Agent 被擋（先.一〇三-1b-3）",
            "blocked_scripts": blocked,
            "warning": (WARNING_TEXT + f"（{'、'.join(blocked)}）") if blocked else None,
            "scripts": dict(sorted(scripts.items())),
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        if n403:
            print(f"::warning::{SCRIPT}：SEC 回 403 共 {n403} 次——{WARNING_TEXT}")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::sec_http_guard 寫檔失敗（不影響抓取）：{type(e).__name__}: {e}")


try:
    _install()
    atexit.register(_flush)
except Exception as _e:  # noqa: BLE001
    print(f"::warning::sec_http_guard 啟用失敗（不影響抓取）：{type(_e).__name__}: {_e}")
