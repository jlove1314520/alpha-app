"""常備.開發-30（2026-10-11）：永豐 API 公告卡（本機唯讀）。

來源：research/telegram_reader.py 每日產生的 digest_YYYY-MM-DD.md（在 repo 外的 C:\\alpha\\telegram_export\\sinopac_api\\）。
只挑「維護／版本／停機」相關的關鍵句，回傳最近 N 則給 alpha_live_server.py 的 GET /sinopac/notices（token 必檢）。

設計（照交辦「只在本機，不進 repo、不轉載原文」）：
- 不另存任何檔案；每次請求即時讀 digest，結果只走本機伺服器回應，不寫進 repo。
- 不轉載原文：只回「含關鍵字的那一句」並截到 KEY_SENTENCE_MAX 字，不回整則訊息，也不回發言者身分（digest 本來就只有官方／一般標記）。
- digest 讀不到／格式不符只略過該行，不拋錯（守門員失敗只降級，CLAUDE.md 第十二節）。
"""
from __future__ import annotations

import re
from pathlib import Path

EXPORT_DIR = Path(r"C:\alpha\telegram_export\sinopac_api")
# digest 的「維護公告」「版本更新」兩段才看；再用較窄的關鍵字過濾，排除「公告」「更新」這類太寬的命中
SECTIONS = ("維護公告", "版本更新")
# 2026-10-11 實測：單用「版本」會抓到大量使用者提問（「你用哪個版本」），故只認公告型措辭
KEYWORDS = re.compile(r"維護|停機|maintenance|暫停服務|停止服務|系統升級|版本(?:更新|發布|發佈|釋出|上線)|新版(?:本)?(?:已|發布|發佈|釋出|上線)|"
                      r"(?:發布|發佈|釋出|上線)[^。]{0,12}(?:版|v\d)|release[sd]?\b|breaking ?change|棄用|deprecat", re.I)
KEY_SENTENCE_MAX = 60
SCAN_DAYS = 30
_LINE = re.compile(r"^- #(\d+) (\d{2}:\d{2}) \[(官方|一般)\] (.*)$")
_SPLIT = re.compile(r"(?<=[。！？!?；;\n])\s*|\s{2,}")


def key_sentence(text: str) -> str | None:
    """回傳第一個含關鍵字的句子（截斷），沒有就 None。"""
    for s in _SPLIT.split(text or ""):
        s = s.strip()
        if s and KEYWORDS.search(s):
            return s if len(s) <= KEY_SENTENCE_MAX else s[:KEY_SENTENCE_MAX] + "…"
    return None


def parse_digest(path: Path) -> list[dict]:
    day = path.stem.replace("digest_", "")
    out, cur, seen = [], None, set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return out
    for ln in lines:
        if ln.startswith("## "):
            cur = ln[3:].split("（")[0].strip()
            continue
        if cur not in SECTIONS:
            continue
        m = _LINE.match(ln)
        if not m or m.group(1) in seen:
            continue
        ks = key_sentence(m.group(4))
        if not ks:
            continue
        seen.add(m.group(1))
        out.append({"date": day, "time": m.group(2), "msg_id": int(m.group(1)),
                    "role": m.group(3), "category": cur, "sentence": ks})
    return out


def recent_notices(limit: int = 5, export_dir: Path = EXPORT_DIR) -> dict:
    if not export_dir.exists():
        return {"items": [], "available": False, "reason": "本機沒有永豐群組擷取資料夾（telegram_reader 尚未啟用）"}
    files = sorted(export_dir.glob("digest_*.md"), reverse=True)[:SCAN_DAYS]
    items: list[dict] = []
    for f in files:
        items.extend(parse_digest(f))
    items.sort(key=lambda x: (x["date"], x["time"], x["msg_id"]), reverse=True)
    latest = files[0].stem.replace("digest_", "") if files else None
    return {"items": items[:max(1, min(int(limit), 20))], "available": bool(files),
            "latest_digest": latest, "scanned_days": len(files),
            "reason": None if files else "尚無每日摘要"}


if __name__ == "__main__":
    import json, sys
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(json.dumps(recent_notices(), ensure_ascii=False, indent=1))
