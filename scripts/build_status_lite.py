"""先.一三五-1kh-i（2026-11-04）：從 data/STATUS.json 抽出首頁啟動時真正用到的欄位，寫成 data/status_lite.json。

背景：首頁首次載入（冒煙 #78，門檻 350KB）原本下載整份 STATUS.json（gzip 約 20KB），
但首頁只用到三樣東西：
  1. workflows 裡 market.yml 那一列（診斷橫幅「下次排程」時間，app.js marketScheduleLabel）
  2. data_files 裡 data/fundamentals.json 那一列的 generated_at（診斷橫幅基本面新鮮度）
  3. local_schedule_heartbeat.claude_auth（Claude 授權／額度紅色橫幅）
STATUS.json 每輪都有人往 known_limitations／data_files 加字、會一直長，所以首頁改讀這份小檔；
設定頁與研究方法頁照舊讀整份 STATUS.json。

呼叫端：scripts/check_local_schedule_heartbeat.py（雲端每 30 分鐘）與 generate_status_json.py（market.yml），
兩者寫完 STATUS.json 後呼叫 write_status_lite()。本支自身失敗只印警告、不拋錯（CLAUDE.md 十二節），
App 端讀不到 lite 會退回整份 STATUS.json。只用標準函式庫、零外部請求。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = REPO_ROOT / "data" / "STATUS.json"
LITE_PATH = REPO_ROOT / "data" / "status_lite.json"


def build_lite(doc: dict) -> dict:
    wfs = doc.get("workflows") if isinstance(doc.get("workflows"), list) else []
    dfs = doc.get("data_files") if isinstance(doc.get("data_files"), list) else []
    lsh = doc.get("local_schedule_heartbeat") if isinstance(doc.get("local_schedule_heartbeat"), dict) else {}
    lite_lsh = {}
    if "claude_auth" in lsh:
        lite_lsh["claude_auth"] = lsh["claude_auth"]
    return {
        "_note": "由 scripts/build_status_lite.py 從 data/STATUS.json 抽出首頁用的欄位；完整內容看 STATUS.json",
        "source_updated_at": doc.get("updated_at"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workflows": [w for w in wfs if isinstance(w, dict) and str(w.get("file", "")).endswith("market.yml")],
        "data_files": [x for x in dfs if isinstance(x, dict) and x.get("path") == "data/fundamentals.json"],
        "local_schedule_heartbeat": lite_lsh,
    }


def write_status_lite(status_path: Path = STATUS_PATH, lite_path: Path = LITE_PATH) -> bool:
    """成功回 True；任何失敗只印警告回 False（不拋錯，十二節）。"""
    try:
        doc = json.loads(Path(status_path).read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise ValueError("STATUS.json 頂層不是物件")
        lite = build_lite(doc)
        tmp = Path(lite_path).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(lite, ensure_ascii=False, indent=1), encoding="utf-8")
        json.loads(tmp.read_text(encoding="utf-8"))  # 寫檔前驗
        tmp.replace(lite_path)
        return True
    except Exception as e:  # noqa: BLE001 -- 守門員自身失敗只降級
        print(f"::warning::status_lite.json 產生失敗（首頁會退回讀整份 STATUS.json）：{type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    ok = write_status_lite()
    print("status_lite.json 已更新" if ok else "status_lite.json 未更新")
    sys.exit(0)
