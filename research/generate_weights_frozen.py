"""一次性產生 `weights_frozen.json` 的工具腳本（2026-08-26 新增，使用者「上線評分路徑」
規格要求）。**只在第一次凍結、或使用者明確同意要更新權重時才手動執行**——平常
`score_live.py` 只讀這個檔案，不會、也不允許重新產生它（見該檔案的寫入防護）。

執行方式：`python generate_weights_frozen.py`，會覆寫 `weights_frozen.json`（如果
已存在，印出警告要求使用者確認這是刻意的動作，不會靜默覆蓋）。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from score_v2 import FACTOR_DEFS
from validation.holdout import TRAIN_END, VAL_END

TW_TZ = timezone(timedelta(hours=8))
OUT_PATH = Path(__file__).parent / "weights_frozen.json"


def build_frozen_payload() -> dict:
    weights = {k: v["weight"] for k, v in FACTOR_DEFS.items()}
    weights_json = json.dumps(weights, sort_keys=True)
    weights_sha256 = hashlib.sha256(weights_json.encode("utf-8")).hexdigest()
    return {
        "engine_version": "score_v2.1-frozen",
        "frozen_at": datetime.now(TW_TZ).strftime("%Y-%m-%d"),
        "dev_period": {"train_end": TRAIN_END, "val_end": VAL_END},
        "source": r"docs\Alpha_評分引擎_10分制設計小抄.md 第三節，score_v2.py::FACTOR_DEFS 原始常數的一次性快照",
        "weights": weights,
        "weights_sha256": weights_sha256,
    }


def main():
    if OUT_PATH.exists():
        print(f"警告：{OUT_PATH} 已存在。這支腳本設計上只給第一次凍結用，"
              "更新既有凍結權重需要使用者明確同意並記錄理由（見 PORTFOLIO_STRATEGY_SPEC.md/"
              "MARATHON_STATE.md 對「凍結後禁止事後調整」的規則精神）。加 --force 才會覆寫。")
        if "--force" not in sys.argv:
            sys.exit(1)
        print("收到 --force，覆寫既有檔案。")

    payload = build_frozen_payload()
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已寫入 {OUT_PATH}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
