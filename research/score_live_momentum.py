"""題材動能榜的上線評分路徑權重管理（2026-08-27新增）。

**背景（使用者裁示，策略層面決定）**：現行評分引擎（`score_v2.py`/
`generate_scores_live.py`）財報回顧類因子合計48%權重+估值因子(PEG)12%會
反向懲罰股價領先財報的題材股，導致AI供應鏈題材股幾乎不上榜——這不是bug，
是權重設計本身的結構性偏好。使用者裁示：**不要用單一分數通吃，拆成兩個
獨立榜單**，價值成長榜（現行引擎，不動）+ 題材動能榜（這支檔案+
`generate_scores_momentum.py`，全新因子與權重）。

**跟`score_live.py`（價值成長榜的權重管理）的關係——各自獨立版本控管**
（使用者原話）：這支檔案是完全獨立的複製品，保護`weights_frozen_momentum.json`
而不是`weights_frozen.json`，兩份權重檔互不影響、各自的寫入防護分開安裝。
不修改`score_live.py`本身，避免任何風險波及已經在用的價值成長榜pipeline。

**硬性禁止（跟score_live.py同一套規則）**：這支檔案不得寫入
`weights_frozen_momentum.json`，不得做任何形式的擬合/最佳化/重新校準。
`_install_no_write_guard_momentum()`在import時自動啟動。

**極重要，使用者原話**：「兩個榜單都必須各自回測驗證（BACKLOG B16提升為
P0）。在回測完成前，兩個榜單頁面都要標明：本榜為資料排序，尚未經過組合
策略回測驗證，不代表能贏大盤。」這份`weights_frozen_momentum.json`目前
是**專家判斷的初始設計權重，不是回測最佳化後的結果**——`frozen_at`欄位
不代表「已驗證鎖定」，只代表「這是目前使用的版本」，回測完成、使用者
同意後才能視為正式驗證過的權重。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from pathlib import Path

WEIGHTS_FROZEN_MOMENTUM_PATH = Path(__file__).parent / "weights_frozen_momentum.json"

_guard_installed = False


def _install_no_write_guard_momentum() -> None:
    """跟score_live.py的_install_no_write_guard()同一套機制，只是保護的檔案
    換成weights_frozen_momentum.json——monkey-patch pathlib.Path.write_text/
    write_bytes，任何嘗試寫入這個檔案的動作立刻拋例外中止。"""
    global _guard_installed
    if _guard_installed:
        return

    frozen_resolved = WEIGHTS_FROZEN_MOMENTUM_PATH.resolve()
    original_write_text = pathlib.Path.write_text
    original_write_bytes = pathlib.Path.write_bytes

    def guarded_write_text(self: pathlib.Path, *args, **kwargs):
        if self.resolve() == frozen_resolved:
            raise RuntimeError(
                "score_live_momentum.py 硬性規則被觸發：偵測到嘗試寫入 "
                "weights_frozen_momentum.json（write_text）。這支「上線評分路徑」"
                "唯讀權重檔，不得做任何形式的擬合/校準/調整。更新凍結權重必須回到"
                "研究路徑重新驗證（B16回測），並經使用者明確同意後才能重新產生。"
            )
        return original_write_text(self, *args, **kwargs)

    def guarded_write_bytes(self: pathlib.Path, *args, **kwargs):
        if self.resolve() == frozen_resolved:
            raise RuntimeError(
                "score_live_momentum.py 硬性規則被觸發：偵測到嘗試寫入 "
                "weights_frozen_momentum.json（write_bytes）。同上，拒絕執行。"
            )
        return original_write_bytes(self, *args, **kwargs)

    pathlib.Path.write_text = guarded_write_text
    pathlib.Path.write_bytes = guarded_write_bytes
    _guard_installed = True


_install_no_write_guard_momentum()


def load_frozen_weights_momentum() -> dict:
    """讀取weights_frozen_momentum.json，驗證內容雜湊，回傳整份凍結內容。"""
    if not WEIGHTS_FROZEN_MOMENTUM_PATH.exists():
        raise RuntimeError(
            f"{WEIGHTS_FROZEN_MOMENTUM_PATH} 不存在——第一次使用前要先手動建立這份"
            "初始設計權重檔（見該檔案note欄位說明：這是專家判斷的起始值，不是"
            "回測最佳化結果）。"
        )
    frozen = json.loads(WEIGHTS_FROZEN_MOMENTUM_PATH.read_text(encoding="utf-8"))
    weights_json = json.dumps(frozen["weights"], sort_keys=True)
    computed_hash = hashlib.sha256(weights_json.encode("utf-8")).hexdigest()
    if computed_hash != frozen["weights_sha256"]:
        raise RuntimeError(
            f"weights_frozen_momentum.json 內容跟記錄的 sha256 不符"
            f"（記錄={frozen['weights_sha256']}，實際算出={computed_hash}）——"
            "可能被竄改或手動編輯過，拒絕使用這份權重。"
        )
    total = sum(frozen["weights"].values())
    if abs(total - 1.0) > 1e-9:
        raise RuntimeError(f"凍結權重加總不是 1.0（{total}），拒絕使用")
    return frozen
