# -*- coding: utf-8 -*-
"""自測：冒煙測試記憶體保護（先.一三八-B3）。注入假記憶體值測兩條路徑，.mjs 與 .py 兩版都測。
不跑真的冒煙（足夠記憶體的路徑只測守門員函式本身，不啟動瀏覽器）。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
fails = 0


def check(name, cond, extra=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + (f"（{extra}）" if extra else ""))
    fails += 0 if cond else 1


def run(cmd, fake):
    env = dict(os.environ, ALPHA_SMOKE_FAKE_FREEMEM_MB=fake, ALPHA_SMOKE_MEM_WAIT_MS="10", PYTHONIOENCODING="utf-8")
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    return r.returncode, r.stdout + r.stderr


# .mjs：整支腳本，兩次都不足 → 非 0、明寫未執行、沒有「全部通過」
rc, out = run(["node", "scripts/smoke_test.mjs"], "500,600")
check(".mjs 兩次都 <1.5GB → exit 3、不算通過", rc == 3 and "記憶體不足、未執行" in out and "全部通過" not in out, f"rc={rc}")
# .mjs 守門員函式：第 1 次不足、第 2 次足夠 → ok、retried；足夠 → 不等待
js = ("import {memGuard} from './scripts/smoke_mem_guard.mjs';"
      "let n=0;const v=[800,4000];let slept=0;"
      "const a=await memGuard({read:()=>v[n++],sleep:async(ms)=>{slept=ms},waitMs:600000,log:()=>{}});"
      "const b=await memGuard({read:()=>9000,sleep:async()=>{throw new Error('不該等')},waitMs:1,log:()=>{}});"
      "console.log(JSON.stringify({a,b,slept}))")
r = subprocess.run(["node", "--input-type=module", "-e", js], cwd=ROOT, capture_output=True, encoding="utf-8", timeout=60)
check(".mjs 第一次不足等 10 分鐘、重量足夠 → 照常執行", '"a":{"ok":true' in r.stdout and '"retried":true' in r.stdout
      and '"slept":600000' in r.stdout, r.stdout.strip()[:200] or r.stderr[:200])
check(".mjs 記憶體足夠 → 不等待直接執行", '"b":{"ok":true,"free_mb":9000,"retried":false}' in r.stdout)

# .py：整支腳本兩次不足 → exit 3
rc, out = run([sys.executable, "scripts/smoke_test.py"], "500,600")
check(".py 兩次都 <1.5GB → exit 3、不算通過", rc == 3 and "記憶體不足、未執行" in out and "全部通過" not in out, f"rc={rc}")
import smoke_test as S  # noqa: E402
seq = iter([800, 4000])
slept = []
res = S.mem_guard(read=lambda: next(seq), sleep=slept.append, wait_sec=600)
check(".py 第一次不足等 10 分鐘、重量足夠 → 照常執行", res["ok"] and res["retried"] and slept == [600])
res = S.mem_guard(read=lambda: 9000, sleep=lambda s: (_ for _ in ()).throw(AssertionError("不該等")), wait_sec=1)
check(".py 記憶體足夠 → 不等待直接執行", res == {"ok": True, "free_mb": 9000, "retried": False})
check(".py 真實讀值可用", S._free_mb() > 0, f"{S._free_mb():.0f}MB")

print(f"\n{'全部通過' if not fails else f'{fails} 項失敗'}")
sys.exit(1 if fails else 0)
