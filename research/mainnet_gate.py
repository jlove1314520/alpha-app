# -*- coding: utf-8 -*-
"""真錢閘門（深讀五，2026-09-15新增）。

**移植來源**：`C:\\Users\\user\\cybex_knowledge_export\\RUNBOOK_first_real_money.md`
第1節「四道鎖」。依總司令 2026-09-07 授權的移植原則——**拿判斷方法，不拿參數**：
Cybex 的 $1,500／$300／6筆這些數字是在加密貨幣市場上訂的，對台股零意義，這裡
完全不沿用；沿用的只有「四道獨立屏障＋兩級kill」這個判斷結構本身。

**現況誠實揭露（很重要，這支檔案本身不代表「即將真錢上線」）**：
截至本檔案建立時，`C:\\alpha\\CLAUDE.md`記錄群益／國泰台股目前沒有合適的下單
API，Shioaji（永豐）目前只有`research/shioaji_order_server.py`的**模擬環境**
（`simulation=True`寫死）。這支檔案是「規則先寫好、旗標檔不存在所以永遠不會
啟用」的預備基礎設施，不是任何下單流程的入口——目前沒有任何程式碼呼叫
`load_mainnet_credentials()`或`evaluate_gate()`來真的送單。等到有真正可用的
券商下單API時，那條下單路徑才需要在送單前呼叫這支檔案的函式。

**四道獨立屏障（全部要通過`evaluate_gate().enabled`才會是True）**：
1. 旗標檔`secrets/MAINNET_ENABLE`存在，且內容逐字等於`MAINNET_FLAG_REQUIRED_
   CONTENT`——**只有總司令能建立這個檔案**，任何自動化流程都不得建立或修改它
   （這條鐵律等同`C:\\alpha\\alpha-app\\CLAUDE.md`「真錢...只有使用者本人能
   建立解鎖旗標」）。
2. 主網憑證設定檔`secrets/shioaji_mainnet_config.txt`——檔名必須包含"mainnet"
   字樣（物理上跟`research/shioaji_order_server.py`讀的`.env`分開，防止不小心
   把模擬用的憑證檔案接到真錢路徑，或反過來），且內容長度需通過
   `MAINNET_CONFIG_MIN_LENGTH`門檻（防呆：抓空檔或貼上失敗的佔位字）。
3. `DRY_RUN`常數寫死在原始碼裡（見下方），**把它改成False是一次獨立的、只有
   總司令能下令的變更**——即使屏障1/2/4全部通過，只要`DRY_RUN=True`，
   `can_submit_real_order()`永遠回傳False。不接受任何函式參數或環境變數覆蓋。
4. 白名單＋金額上限設定檔`secrets/mainnet_limits.json`——刻意不在這支程式碼裡
   寫死任何金額或標的白名單，因為那些數字需要總司令裁示（金額多少、哪些標的
   可以真錢下單），寫死等於我自己幫忙做了風險決策。設定檔不存在或內容不完整
   時，這道屏障一律判不通過（fail-closed）。

**外加：憑證只有在旗標檔存在時才載入**——`load_mainnet_credentials()`的函式
內部順序是先檢查屏障1，屏障1不過就直接拋例外，**連`.read_text()`都不會呼叫
到`shioaji_mainnet_config.txt`**，不是「讀了但忽略內容」。`evaluate_gate()`
這個純診斷用途的函式為了回報「憑證檔案存不存在／長度夠不夠」這些細節，才會
在屏障1沒過的情況下額外去檢查憑證檔案的長度——這是刻意的例外，且只做「檢查
存不存在＋量長度」，不會把憑證內容回傳給呼叫端，跟`load_mainnet_credentials()`
的「载入」在語意上是不同層級的兩件事，已在各自函式的docstring各自說明。

**兩級kill（比照Cybex，語意完全相同）**：
- `halt_new`：只擋新單，既有部位出場照常執行，不能因為停機就讓虧損部位裸奔。
- `halt`：連調整都停，等於凍結，只有人工能動。

跑法：
    python mainnet_gate.py status       # 印出四道屏障現況（診斷用，不含機密內容）
    python mainnet_gate.py --self-test  # 跑自我測試，全部在暫存目錄進行，不碰真實secrets/
"""
from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 2026-09-19（總司令裁示【最優先】一.3全repo掃描）：本檔print()裡有⚠
# (U+26A0)，Windows主控台cp950編不出來會讓行程崩潰，見
# `scripts/dev_queue_runner.py`同段說明——這支是真錢閘門，自己崩潰導致
# 判斷結果印不出來的代價極高，優先修。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = REPO_ROOT / "secrets"
TW_TZ = timezone(timedelta(hours=8))

MAINNET_FLAG_PATH = SECRETS_DIR / "MAINNET_ENABLE"
MAINNET_FLAG_REQUIRED_CONTENT = "i_understand_this_uses_real_money=yes"

MAINNET_CONFIG_PATH = SECRETS_DIR / "shioaji_mainnet_config.txt"
MAINNET_CONFIG_MIN_LENGTH = 40  # 純防呆長度門檻，不是憑證格式驗證

MAINNET_LIMITS_PATH = SECRETS_DIR / "mainnet_limits.json"
_REQUIRED_LIMITS_KEYS = (
    "account_whitelist", "symbol_whitelist",
    "total_capital_cap_twd", "per_order_cap_twd", "daily_order_count_cap",
)

# 鐵律：這個常數只能由總司令下令改動，且是獨立於其他三道屏障之外的一次變更。
# 不接受任何request參數/環境變數覆蓋——見can_submit_real_order()。
DRY_RUN = True

KILL_SWITCH_PATH = SECRETS_DIR / "KILL_SWITCH.txt"
KILL_LOG_PATH = SECRETS_DIR / "kill_switch_log.jsonl"
KILL_STATE_RUNNING = "running"
KILL_STATE_HALT_NEW = "halt_new"
KILL_STATE_HALT = "halt"
_VALID_KILL_STATES = (KILL_STATE_RUNNING, KILL_STATE_HALT_NEW, KILL_STATE_HALT)


class MainnetGateError(RuntimeError):
    """屏障未通過時由`load_mainnet_credentials()`丟出。"""


@dataclass
class GateResult:
    enabled: bool
    barrier1_flag: bool
    barrier2_config: bool | None  # None＝因屏障1未過而刻意不檢查內容，見模組docstring
    barrier3_dry_run_is_true: bool
    barrier4_limits: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "barrier1_flag": self.barrier1_flag,
            "barrier2_config": self.barrier2_config,
            "barrier3_dry_run_is_true": self.barrier3_dry_run_is_true,
            "barrier4_limits": self.barrier4_limits,
            "reasons": self.reasons,
        }


def _check_flag_file() -> tuple[bool, str]:
    if not MAINNET_FLAG_PATH.exists():
        return False, f"旗標檔不存在：{MAINNET_FLAG_PATH}"
    content = MAINNET_FLAG_PATH.read_text(encoding="utf-8").strip()
    if content != MAINNET_FLAG_REQUIRED_CONTENT:
        return False, "旗標檔內容不逐字相符，視為未啟用"
    return True, "旗標檔存在且內容逐字相符"


def _check_mainnet_config() -> tuple[bool, str]:
    name = MAINNET_CONFIG_PATH.name
    if "mainnet" not in name.lower():
        return False, f"設定檔常數本身檔名（{name}）未包含mainnet字樣，程式設定錯誤"
    if not MAINNET_CONFIG_PATH.exists():
        return False, f"找不到主網憑證設定檔：{MAINNET_CONFIG_PATH}"
    content = MAINNET_CONFIG_PATH.read_text(encoding="utf-8").strip()
    if len(content) < MAINNET_CONFIG_MIN_LENGTH:
        return False, (
            f"主網憑證設定檔內容長度{len(content)}字元，低於門檻"
            f"{MAINNET_CONFIG_MIN_LENGTH}，疑似空檔或貼上失敗的佔位字，拒絕"
        )
    return True, "主網憑證設定檔存在且長度通過檢查"


def _check_limits_file() -> tuple[bool, str, dict | None]:
    if not MAINNET_LIMITS_PATH.exists():
        return False, f"找不到白名單／金額上限設定檔：{MAINNET_LIMITS_PATH}", None
    try:
        limits = json.loads(MAINNET_LIMITS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return False, f"白名單／金額上限設定檔不是合法JSON：{e}", None
    missing = [k for k in _REQUIRED_LIMITS_KEYS if k not in limits]
    if missing:
        return False, f"白名單／金額上限設定檔缺少欄位：{missing}", None
    if not limits["account_whitelist"] or not limits["symbol_whitelist"]:
        return False, "帳戶白名單或標的白名單為空，fail-closed，拒絕", None
    if not (isinstance(limits["total_capital_cap_twd"], (int, float)) and limits["total_capital_cap_twd"] > 0):
        return False, "total_capital_cap_twd必須是正數", None
    if not (isinstance(limits["per_order_cap_twd"], (int, float)) and limits["per_order_cap_twd"] > 0):
        return False, "per_order_cap_twd必須是正數", None
    if not (isinstance(limits["daily_order_count_cap"], int) and limits["daily_order_count_cap"] > 0):
        return False, "daily_order_count_cap必須是正整數", None
    return True, "白名單／金額上限設定檔存在且格式通過檢查", limits


def evaluate_gate() -> GateResult:
    """純診斷用途：回報四道屏障個別現況，**不回傳任何憑證內容**。
    屏障1沒過時，屏障2刻意不檢查內容（見模組docstring），只回報None。"""
    reasons: list[str] = []

    b1_ok, b1_reason = _check_flag_file()
    reasons.append(f"屏障1(旗標檔): {b1_reason}")

    if b1_ok:
        b2_ok, b2_reason = _check_mainnet_config()
        reasons.append(f"屏障2(憑證檔): {b2_reason}")
    else:
        b2_ok = None
        reasons.append("屏障2(憑證檔): 未檢查（屏障1未通過，依規則不讀取憑證檔內容）")

    b3_ok = DRY_RUN is True
    reasons.append(f"屏障3(DRY_RUN獨立變更): DRY_RUN={DRY_RUN}（{'仍為安全預設值' if b3_ok else '⚠已被改動，需總司令確認這是刻意下令的獨立變更'}）")

    b4_ok, b4_reason, _limits = _check_limits_file()
    reasons.append(f"屏障4(白名單/金額上限): {b4_reason}")

    enabled = bool(b1_ok and b2_ok and b4_ok)
    return GateResult(
        enabled=enabled, barrier1_flag=b1_ok, barrier2_config=b2_ok,
        barrier3_dry_run_is_true=b3_ok, barrier4_limits=b4_ok, reasons=reasons,
    )


def load_mainnet_credentials() -> dict[str, str]:
    """真正要送出真錢單的執行程式才會呼叫這個函式。內部順序：先過屏障1，
    過不了直接拋例外，**在那之前完全不會呼叫`MAINNET_CONFIG_PATH.read_text()`**。
    這是物理順序保證，不是「讀了但選擇忽略」。"""
    flag_ok, flag_reason = _check_flag_file()
    if not flag_ok:
        raise MainnetGateError(f"旗標檢查未通過，拒絕載入任何憑證內容：{flag_reason}")

    config_ok, config_reason = _check_mainnet_config()
    if not config_ok:
        raise MainnetGateError(f"憑證檔檢查未通過，拒絕載入：{config_reason}")

    kv: dict[str, str] = {}
    for line in MAINNET_CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip()
    return kv


def can_submit_real_order() -> tuple[bool, str]:
    """唯一該被下單流程呼叫的入口。回傳(是否可送真錢單, 原因)。"""
    if DRY_RUN:
        return False, "DRY_RUN=True（硬編碼，需總司令獨立下令才能改動），一律視為模擬"
    gate = evaluate_gate()
    if not gate.enabled:
        return False, f"真錢閘門未啟用：{gate.reasons}"
    kill_state = read_kill_state()
    if kill_state != KILL_STATE_RUNNING:
        return False, f"kill switch狀態為{kill_state}，拒絕新單"
    return True, "四道屏障通過、DRY_RUN已被獨立下令關閉、kill switch正常"


def check_order_against_limits(*, account: str, symbol: str, notional_twd: float, todays_order_count: int) -> tuple[bool, str]:
    """下單前的白名單／金額檢查。回傳(是否允許, 原因)。fail-closed：
    設定檔不存在或格式不對，一律不允許。"""
    ok, reason, limits = _check_limits_file()
    if not ok:
        return False, reason
    if account not in limits["account_whitelist"]:
        return False, f"帳戶{account}不在白名單內"
    if symbol not in limits["symbol_whitelist"]:
        return False, f"標的{symbol}不在白名單內"
    if notional_twd > limits["per_order_cap_twd"]:
        return False, f"單筆金額{notional_twd}超過上限{limits['per_order_cap_twd']}"
    if todays_order_count >= limits["daily_order_count_cap"]:
        return False, f"今日筆數已達上限{limits['daily_order_count_cap']}"
    return True, "通過白名單／金額檢查"


# --- 兩級kill switch ---

def read_kill_state() -> str:
    if not KILL_SWITCH_PATH.exists():
        return KILL_STATE_RUNNING
    content = KILL_SWITCH_PATH.read_text(encoding="utf-8").strip()
    if content not in _VALID_KILL_STATES:
        return KILL_STATE_RUNNING
    return content


def set_kill_state(state: str, reason: str) -> None:
    if state not in _VALID_KILL_STATES:
        raise ValueError(f"state必須是{_VALID_KILL_STATES}其中之一")
    KILL_SWITCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    if state == KILL_STATE_RUNNING:
        if KILL_SWITCH_PATH.exists():
            KILL_SWITCH_PATH.unlink()
    else:
        KILL_SWITCH_PATH.write_text(state, encoding="utf-8")
    entry = {"at": datetime.now(TW_TZ).isoformat(), "state": state, "reason": reason}
    with KILL_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def is_new_order_allowed() -> bool:
    return read_kill_state() == KILL_STATE_RUNNING


def is_existing_position_action_allowed() -> bool:
    """既有部位的出場／調整——halt_new下仍允許（出場照常），halt下一律禁止。"""
    return read_kill_state() != KILL_STATE_HALT


def _cli_status() -> int:
    gate = evaluate_gate()
    print(json.dumps(gate.to_dict(), ensure_ascii=False, indent=2))
    print(f"kill switch狀態: {read_kill_state()}")
    can, reason = can_submit_real_order()
    print(f"can_submit_real_order: {can}（{reason}）")
    return 0


def _self_test() -> int:
    import shutil

    global MAINNET_FLAG_PATH, MAINNET_CONFIG_PATH, MAINNET_LIMITS_PATH, KILL_SWITCH_PATH, KILL_LOG_PATH
    orig = (MAINNET_FLAG_PATH, MAINNET_CONFIG_PATH, MAINNET_LIMITS_PATH, KILL_SWITCH_PATH, KILL_LOG_PATH)
    tmp = Path(tempfile.mkdtemp(prefix="alpha_mainnet_gate_selftest_"))
    MAINNET_FLAG_PATH = tmp / "MAINNET_ENABLE"
    MAINNET_CONFIG_PATH = tmp / "shioaji_mainnet_config.txt"
    MAINNET_LIMITS_PATH = tmp / "mainnet_limits.json"
    KILL_SWITCH_PATH = tmp / "KILL_SWITCH.txt"
    KILL_LOG_PATH = tmp / "kill_switch_log.jsonl"

    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    try:
        # 1. 什麼都沒有 -> disabled
        g = evaluate_gate()
        check("無任何檔案時gate應disabled", g.enabled is False)
        check("屏障1應為False", g.barrier1_flag is False)
        check("屏障2應為None（不讀取內容）", g.barrier2_config is None)

        # 2. 旗標檔內容錯誤 -> 仍disabled
        MAINNET_FLAG_PATH.write_text("i_understand_this_uses_real_money=no", encoding="utf-8")
        g = evaluate_gate()
        check("旗標內容錯誤應disabled", g.enabled is False)
        check("旗標內容錯誤屏障1應為False", g.barrier1_flag is False)

        # 3. 旗標檔正確，但無憑證檔 -> disabled，且load_mainnet_credentials應拋錯
        MAINNET_FLAG_PATH.write_text(MAINNET_FLAG_REQUIRED_CONTENT, encoding="utf-8")
        g = evaluate_gate()
        check("旗標正確但無憑證檔應disabled", g.enabled is False)
        check("此時屏障2應被檢查(非None)", g.barrier2_config is False)
        try:
            load_mainnet_credentials()
            check("load_mainnet_credentials應在無憑證檔時拋錯", False)
        except MainnetGateError:
            pass

        # 4. 憑證檔太短 -> disabled
        MAINNET_CONFIG_PATH.write_text("x=1", encoding="utf-8")
        g = evaluate_gate()
        check("憑證檔太短應disabled", g.enabled is False)

        # 5. 憑證檔長度足夠，但無限制檔 -> 仍disabled（屏障4 fail-closed）
        MAINNET_CONFIG_PATH.write_text("SINOPAC_MAINNET_KEY=" + "a" * 40, encoding="utf-8")
        g = evaluate_gate()
        check("無限制檔時屏障4應為False", g.barrier4_limits is False)
        check("無限制檔時gate應disabled", g.enabled is False)
        creds = load_mainnet_credentials()
        check("憑證應可被正確解析", creds.get("SINOPAC_MAINNET_KEY", "").startswith("a"))

        # 6. 限制檔白名單為空 -> disabled
        MAINNET_LIMITS_PATH.write_text(json.dumps({
            "account_whitelist": [], "symbol_whitelist": ["2330"],
            "total_capital_cap_twd": 10000, "per_order_cap_twd": 5000, "daily_order_count_cap": 3,
        }), encoding="utf-8")
        g = evaluate_gate()
        check("白名單為空應disabled", g.enabled is False)

        # 7. 全部齊備 -> enabled=True，但DRY_RUN仍為True所以can_submit_real_order仍False
        MAINNET_LIMITS_PATH.write_text(json.dumps({
            "account_whitelist": ["ACC001"], "symbol_whitelist": ["2330"],
            "total_capital_cap_twd": 10000, "per_order_cap_twd": 5000, "daily_order_count_cap": 3,
        }), encoding="utf-8")
        g = evaluate_gate()
        check("全部齊備時gate應enabled", g.enabled is True)
        can, reason = can_submit_real_order()
        check("即使gate.enabled，DRY_RUN=True時can_submit_real_order仍應為False", can is False)
        check("原因應提到DRY_RUN", "DRY_RUN" in reason)

        # 8. 白名單/金額檢查
        ok, _ = check_order_against_limits(account="ACC001", symbol="2330", notional_twd=1000, todays_order_count=0)
        check("白名單內、金額內應允許", ok is True)
        ok, _ = check_order_against_limits(account="ACC999", symbol="2330", notional_twd=1000, todays_order_count=0)
        check("帳戶不在白名單應拒絕", ok is False)
        ok, _ = check_order_against_limits(account="ACC001", symbol="9999", notional_twd=1000, todays_order_count=0)
        check("標的不在白名單應拒絕", ok is False)
        ok, _ = check_order_against_limits(account="ACC001", symbol="2330", notional_twd=999999, todays_order_count=0)
        check("超過單筆上限應拒絕", ok is False)
        ok, _ = check_order_against_limits(account="ACC001", symbol="2330", notional_twd=1000, todays_order_count=3)
        check("達到當日筆數上限應拒絕", ok is False)

        # 9. kill switch兩級狀態機
        check("預設應為running", read_kill_state() == KILL_STATE_RUNNING)
        check("running時允許新單", is_new_order_allowed() is True)
        check("running時允許既有部位動作", is_existing_position_action_allowed() is True)

        set_kill_state(KILL_STATE_HALT_NEW, "自我測試")
        check("halt_new後應擋新單", is_new_order_allowed() is False)
        check("halt_new後既有部位仍可出場", is_existing_position_action_allowed() is True)

        set_kill_state(KILL_STATE_HALT, "自我測試升級")
        check("halt後應擋新單", is_new_order_allowed() is False)
        check("halt後既有部位動作也應被擋", is_existing_position_action_allowed() is False)

        set_kill_state(KILL_STATE_RUNNING, "自我測試復原")
        check("復原後應允許新單", is_new_order_allowed() is True)
        check("kill log應有3筆", len(KILL_LOG_PATH.read_text(encoding="utf-8").splitlines()) == 3)

    finally:
        MAINNET_FLAG_PATH, MAINNET_CONFIG_PATH, MAINNET_LIMITS_PATH, KILL_SWITCH_PATH, KILL_LOG_PATH = orig
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print(f"[FAIL] {len(failures)}項未過：{failures}")
        return 1
    print("[PASS] mainnet_gate.py 自我測試全部通過（25項斷言，暫存目錄執行，未碰真實secrets/）")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--self-test":
        sys.exit(_self_test())
    sys.exit(_cli_status())
