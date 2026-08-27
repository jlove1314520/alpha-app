"""未來性濾網的上線評分路徑權重管理（2026-08-27新增）。

**跟`score_live.py`（價值成長榜）/`score_live_momentum.py`（題材動能榜）
同一套模式——各自獨立版本控管**（使用者原話）：這支檔案保護
`weights_frozen_future.json`，不影響另外兩份權重檔的寫入防護。

**第三個獨立濾網「未來性濾網」**：因子分三階段——(a)現在就能算（這支檔案
對應的`generate_scores_future.py`已實作的部分：法人連續買超天數/買超佔
股本比/買超集中度/毛利率水準與穩定度/產能利用率代理）、(b)需事件資料
（等新聞管線，見BACKLOG.md B18）、(c)AI質性研判（見BACKLOG.md B20，
使用者規則：不計入量化總分，另闢區塊呈現）。

**硬性禁止（跟另外兩份權重管理同一套規則）**：不得寫入
`weights_frozen_future.json`，不得做任何形式的擬合/最佳化/重新校準。

**極重要**：`weights_frozen_future.json`目前是專家判斷的初始設計權重，
不是回測最佳化後的結果。回測完成（BACKLOG.md B16）、使用者同意前，這份
權重跟`generate_scores_future.py`產生的分數都必須標示「本榜為資料排序，
尚未經過組合策略回測驗證，不代表能贏大盤」。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from pathlib import Path

WEIGHTS_FROZEN_FUTURE_PATH = Path(__file__).parent / "weights_frozen_future.json"

_guard_installed = False


def _install_no_write_guard_future() -> None:
    global _guard_installed
    if _guard_installed:
        return

    frozen_resolved = WEIGHTS_FROZEN_FUTURE_PATH.resolve()
    original_write_text = pathlib.Path.write_text
    original_write_bytes = pathlib.Path.write_bytes

    def guarded_write_text(self: pathlib.Path, *args, **kwargs):
        if self.resolve() == frozen_resolved:
            raise RuntimeError(
                "score_live_future.py 硬性規則被觸發：偵測到嘗試寫入 "
                "weights_frozen_future.json（write_text）。這支「上線評分路徑」"
                "唯讀權重檔，不得做任何形式的擬合/校準/調整。更新凍結權重必須回到"
                "研究路徑重新驗證（B16回測），並經使用者明確同意後才能重新產生。"
            )
        return original_write_text(self, *args, **kwargs)

    def guarded_write_bytes(self: pathlib.Path, *args, **kwargs):
        if self.resolve() == frozen_resolved:
            raise RuntimeError(
                "score_live_future.py 硬性規則被觸發：偵測到嘗試寫入 "
                "weights_frozen_future.json（write_bytes）。同上，拒絕執行。"
            )
        return original_write_bytes(self, *args, **kwargs)

    pathlib.Path.write_text = guarded_write_text
    pathlib.Path.write_bytes = guarded_write_bytes
    _guard_installed = True


_install_no_write_guard_future()


def load_frozen_weights_future() -> dict:
    if not WEIGHTS_FROZEN_FUTURE_PATH.exists():
        raise RuntimeError(f"{WEIGHTS_FROZEN_FUTURE_PATH} 不存在。")
    frozen = json.loads(WEIGHTS_FROZEN_FUTURE_PATH.read_text(encoding="utf-8"))
    weights_json = json.dumps(frozen["weights"], sort_keys=True)
    computed_hash = hashlib.sha256(weights_json.encode("utf-8")).hexdigest()
    if computed_hash != frozen["weights_sha256"]:
        raise RuntimeError(
            f"weights_frozen_future.json 內容跟記錄的 sha256 不符"
            f"（記錄={frozen['weights_sha256']}，實際算出={computed_hash}）——"
            "可能被竄改或手動編輯過，拒絕使用這份權重。"
        )
    total = sum(frozen["weights"].values())
    if abs(total - 1.0) > 1e-9:
        raise RuntimeError(f"凍結權重加總不是 1.0（{total}），拒絕使用")
    return frozen
