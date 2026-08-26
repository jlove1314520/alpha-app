"""上線評分路徑（2026-08-26 新增，使用者硬性規格）——選股頁 `scores.json` 唯一
合法的權重來源，跟研究路徑物理分離。

**使用者裁示的核心規則，逐字照抄，不重新詮釋**：「洩漏 holdout 的定義是『用
VAL_END 之後的資料去擬合或調整參數』。只要參數凍結、不再擬合，用凍結參數去計算
新資料的分數，屬於正式的 out-of-sample 應用，不構成洩漏，也不消耗 holdout。」

**雙路徑，互不污染**：
  1. 研究路徑（`finmind_client.load_dev()`／`factor_ic.py`／`TRIALS_LEDGER.md`
     那一整套驗證框架）維持原樣，仍然卡在 `VAL_END`，任何研究/檢定/調參都只能走
     這條——這支檔案完全不碰、也不 import 那條路徑的任何調參邏輯。
  2. 這支檔案是「上線評分路徑」：讀 `weights_frozen.json`（凍結權重，含
     `weights_sha256` 稽核用雜湊）+ 當前最新交易日資料（透過
     `realtime_asof.py::as_of_today()`，機制上暫時拉高 `validation.holdout.VAL_END`
     這個模組屬性，讓 `load_dev()` 等資料層讀到新邊界——這不是繞過 holdout，是
     2026-08-25 使用者裁示已經授權的機制，這支檔案只是把它跟「凍結權重」正式
     綁在一起）算分數，寫回 `scores.json`。

**硬性禁止（使用者原話）**：「這支程式不得寫入任何權重/參數檔，不得做任何形式的
擬合、最佳化、重新校準或門檻調整。」`_install_no_write_guard()` 在 import 這支檔案
時就自動啟動，攔截任何對 `weights_frozen.json` 的寫入嘗試並立刻中止——不是靠
「工程師記得不要這樣做」，是程式碼層面就做不到。

**更新凍結權重的唯一合法方式**：回到研究路徑重新驗證、明確記錄理由（`STRATEGY_LOG.md`
或使用者當輪對話紀錄）、使用者明確同意後，用 `generate_weights_frozen.py --force`
重新產生（那支腳本本身也會印警告要求確認），不是編輯這支檔案或這裡的任何函式。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from pathlib import Path

WEIGHTS_FROZEN_PATH = Path(__file__).parent / "weights_frozen.json"

_guard_installed = False


def _install_no_write_guard() -> None:
    """monkey-patch `pathlib.Path.write_text`/`write_bytes`：任何呼叫端（包含這支
    檔案自己不小心寫錯、或未來有人在這支檔案裡加了不該加的程式碼）嘗試寫入
    `weights_frozen.json`，立刻拋出例外中止，不會靜默成功。只裝這一次（模組
    載入時），重複 import 不會疊加裝好幾層 patch。"""
    global _guard_installed
    if _guard_installed:
        return

    frozen_resolved = WEIGHTS_FROZEN_PATH.resolve()
    original_write_text = pathlib.Path.write_text
    original_write_bytes = pathlib.Path.write_bytes

    def guarded_write_text(self: pathlib.Path, *args, **kwargs):
        if self.resolve() == frozen_resolved:
            raise RuntimeError(
                "score_live.py 硬性規則被觸發：偵測到嘗試寫入 weights_frozen.json（write_text）。"
                "這支「上線評分路徑」唯讀權重檔，不得做任何形式的擬合/校準/調整。"
                "更新凍結權重必須回到研究路徑重新驗證，並用 generate_weights_frozen.py --force"
                "（使用者明確同意後）重新產生，不是從這裡寫入。"
            )
        return original_write_text(self, *args, **kwargs)

    def guarded_write_bytes(self: pathlib.Path, *args, **kwargs):
        if self.resolve() == frozen_resolved:
            raise RuntimeError(
                "score_live.py 硬性規則被觸發：偵測到嘗試寫入 weights_frozen.json（write_bytes）。"
                "同上，拒絕執行。"
            )
        return original_write_bytes(self, *args, **kwargs)

    pathlib.Path.write_text = guarded_write_text
    pathlib.Path.write_bytes = guarded_write_bytes
    _guard_installed = True


_install_no_write_guard()  # import 這支檔案就自動啟動防護，不需要呼叫端記得手動開


def load_frozen_weights() -> dict:
    """讀取 weights_frozen.json，驗證內容雜湊是否跟記錄的一致（不一致代表檔案
    被竄改或損毀，拒絕使用、直接拋例外，不能悄悄用一份可能不正確的權重算分數）。
    回傳整份凍結內容（含 engine_version/frozen_at/dev_period/weights/weights_sha256）。
    """
    if not WEIGHTS_FROZEN_PATH.exists():
        raise RuntimeError(
            f"{WEIGHTS_FROZEN_PATH} 不存在——第一次使用前要先手動執行一次 "
            "generate_weights_frozen.py（不是這支檔案的職責，這支檔案只讀不產生）。"
        )
    frozen = json.loads(WEIGHTS_FROZEN_PATH.read_text(encoding="utf-8"))
    weights_json = json.dumps(frozen["weights"], sort_keys=True)
    computed_hash = hashlib.sha256(weights_json.encode("utf-8")).hexdigest()
    if computed_hash != frozen["weights_sha256"]:
        raise RuntimeError(
            f"weights_frozen.json 內容跟記錄的 sha256 不符（記錄={frozen['weights_sha256']}，"
            f"實際算出={computed_hash}）——可能被竄改或手動編輯過，拒絕使用這份權重。"
        )
    return frozen


def apply_frozen_weights(frozen: dict) -> None:
    """把凍結權重套進 `score_v2.FACTOR_DEFS`（就地覆寫每個因子的 weight 值，
    label/higher_better 等結構不變）——這樣 `compute_scores_v2()`/
    `export_scores_v2_json()` 這些既有、已經測過的計分函式完全不用改，寫進
    `scores.json` 的 `weights` 欄位也會自動反映凍結值，不需要另外同步。

    這個函式本身**只讀取 frozen 傳進來的權重、只修改記憶體內的 dict**，不寫入任何
    檔案——跟上面 `_install_no_write_guard()` 的防護是兩件獨立的事：這裡是「不做
    擬合」的部分，防護是「就算不小心寫也會被攔下來」的第二道保險。
    """
    import score_v2

    for key, w in frozen["weights"].items():
        if key not in score_v2.FACTOR_DEFS:
            raise RuntimeError(f"weights_frozen.json 有 score_v2.FACTOR_DEFS 沒有的因子鍵：{key!r}")
        score_v2.FACTOR_DEFS[key]["weight"] = w
    missing = set(score_v2.FACTOR_DEFS) - set(frozen["weights"])
    if missing:
        raise RuntimeError(f"weights_frozen.json 缺少 score_v2.FACTOR_DEFS 有的因子鍵：{missing}")
    total = sum(v["weight"] for v in score_v2.FACTOR_DEFS.values())
    if abs(total - 1.0) > 1e-9:
        raise RuntimeError(f"凍結權重加總不是 1.0（{total}），拒絕使用")


def weights_hash() -> str:
    """回傳目前 weights_frozen.json 的 sha256（`generate_scores_v2.py` 用來寫進
    `scores.json` 的 `meta.weights_hash`，供日後稽核用）。"""
    frozen = load_frozen_weights()
    return frozen["weights_sha256"]
