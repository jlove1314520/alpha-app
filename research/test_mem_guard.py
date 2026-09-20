"""驗收腳本（2026-09-20總司令裁示【記憶體事故記錄不精確...安全閥可能
根本沒實作】三.3）：故意讓`mem_guard`的門檻判定為「已經低於門檻」，
實證它**真的會終止行程**，不是只宣稱會——跟`net_guard`/
`test_net_guard.py`同一種「用monkeypatch製造觸發條件、實測行為，
不是只看程式碼推論」的驗收精神。

**測試設計**：不真的把機器記憶體榨到3GB以下（那樣做本身就會重演
事件001的風險，且測試會變慢、不穩定），而是在一支子行程裡把
`mem_guard.MIN_FREE_BYTES`（白箱測試合理调整，不是「執行期間動態
調整生產門檻」——生產腳本本身從頭到尾都不會改這個常數）覆寫成一個
保證高於目前真實可用記憶體的天文數字，讓下一次背景執行緒檢查時
必定判定「低於門檻」，藉此驗證`os._exit(1)`真的被呼叫、子行程真的
以非0結束碼終止，而不是繼續正常執行。
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

CHILD_SCRIPT = textwrap.dedent("""
    import sys
    sys.path.insert(0, r"{research_dir}")
    import mem_guard

    # 白箱測試覆寫：保證觸發（門檻設成不可能滿足的天文數字），
    # 只在這支子行程的獨立記憶體空間裡生效，不影響其他行程或母行程。
    mem_guard.MIN_FREE_BYTES = 10**18
    mem_guard.CHECK_INTERVAL_SECONDS = 1

    ok = mem_guard.install()
    assert ok, "mem_guard.install() 回傳False，代表平台判定不支援，測試環境不對"

    # 正常情況下這支子行程應該在CHECK_INTERVAL_SECONDS內被mem_guard
    # 用os._exit(1)強制終止；如果安全閥沒有真的動作，這裡的sleep會
    # 跑完然後行程以exit code 0正常結束，測試就能分辨出兩種情況。
    import time
    time.sleep(10)
    print("MEM_GUARD_DID_NOT_TRIGGER")  # 不應該執行到這一行
    sys.exit(0)
""")


def test_mem_guard_actually_terminates_process() -> None:
    research_dir = str(Path(__file__).parent)
    script = CHILD_SCRIPT.format(research_dir=research_dir.replace("\\", "\\\\"))
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=20,
    )
    assert "MEM_GUARD_DID_NOT_TRIGGER" not in result.stdout, (
        "mem_guard沒有真的終止子行程——安全閥形同虛設，"
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.returncode != 0, (
        f"子行程以exit code {result.returncode}結束（非預期的os._exit(1)=1），"
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "低於門檻" in result.stderr, (
        f"子行程結束了，但stderr沒有看到mem_guard自己印的終止訊息，"
        f"無法確認是mem_guard做的而不是其他原因意外死掉：stderr={result.stderr!r}"
    )
    print("test_mem_guard: 子行程在門檻被故意設成保證觸發後，"
          f"真的被mem_guard用os._exit(1)終止（exit code={result.returncode}），"
          "不是只宣稱會擋下。")


def test_normal_threshold_does_not_kill_healthy_process() -> None:
    """對照組：門檻維持正常值（3GB）時，一個記憶體用量正常的行程不該
    被誤殺——避免只驗證「會觸發」卻沒驗證「不誤觸發」。"""
    research_dir = str(Path(__file__).parent)
    script = textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, r"{research_dir}")
        import mem_guard
        mem_guard.CHECK_INTERVAL_SECONDS = 1
        ok = mem_guard.install()
        assert ok
        time.sleep(3)
        print("SURVIVED")
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, (
        f"正常門檻下健康行程不應該被終止，卻以exit code {result.returncode}結束："
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "SURVIVED" in result.stdout
    print("test_mem_guard: 正常門檻（3GB）下，記憶體用量正常的行程沒有被誤殺。")


if __name__ == "__main__":
    test_mem_guard_actually_terminates_process()
    test_normal_threshold_does_not_kill_healthy_process()
