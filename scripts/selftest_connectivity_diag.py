# -*- coding: utf-8 -*-
"""先.十一-三 自測：斷線分類規則、診斷自身失敗時 fail open、卡死時 watchdog 留紀錄。
用法：python scripts/selftest_connectivity_diag.py（不寫正式 LOG/STATE）"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_external_connectivity as c  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


A = {"ok": True, "answered": True, "detail": "x"}
B = {"ok": False, "detail": "無回應"}
base = {"direct_dns": {"1.1.1.1": A, "8.8.8.8": A}, "system_dns": A, "gateway": {"ip": "192.168.1.1", "ok": True},
        "tailscale": {"backend": "Running", "magic_dns": True}, "tailscale_dns": A}

check("正常", c.classify_outage(True, base)[0] == "正常")
check("整條外網斷:直連DNS皆不通", c.classify_outage(False, {**base, "direct_dns": {"1.1.1.1": B, "8.8.8.8": B}, "system_dns": B})[0] == "整條外網斷")
check("整條外網斷:無預設路由", c.classify_outage(False, {**base, "direct_dns": {"1.1.1.1": B, "8.8.8.8": B}, "gateway": {"ip": None, "ok": False}})[1].find("無預設閘道") >= 0)
check("只有DNS壞", c.classify_outage(False, {**base, "system_dns": B})[0] == "只有DNS壞")
check("只有DNS壞:Tailscale未啟用MagicDNS", c.classify_outage(False, {**base, "system_dns": B, "tailscale": {"backend": "Stopped", "magic_dns": False}, "tailscale_dns": None})[0] == "只有DNS壞")
check("Tailscale接管DNS失敗:100.100.100.100無回應", c.classify_outage(False, {**base, "system_dns": B, "tailscale_dns": B})[0] == "Tailscale接管DNS失敗")
check("Tailscale接管DNS失敗:backend非Running", c.classify_outage(False, {**base, "system_dns": B, "tailscale": {"backend": "Stopped", "magic_dns": True}})[0] == "Tailscale接管DNS失敗")
check("其他:DNS都通但HTTPS失敗", c.classify_outage(False, base)[0] == "其他")

# 注入診斷自身失敗：_run 一律丟例外、UDP/getaddrinfo 一律丟例外 → collect_net_diag 不得丟例外
orig = (c._run, c._dns_query_udp, c._dns_system)


def boom(*a, **k):
    raise RuntimeError("injected")


c._run, c._dns_query_udp, c._dns_system = boom, boom, boom
try:
    d = c.collect_net_diag(False)
    check("注入失敗:不丟例外且有分類", "class" in d)
    check("注入失敗:分類為整條外網斷(直連全失敗)", d["class"] == "整條外網斷")
finally:
    c._run, c._dns_query_udp, c._dns_system = orig

# 逾時：getaddrinfo 卡住 → _bounded 必須在上限內放棄等待
t0 = time.monotonic()
done, _ = c._bounded(lambda: time.sleep(30), 1.0)
check("_bounded 逾時放棄等待(<3s)", (not done) and time.monotonic() - t0 < 3)

# 真實環境一次
d = c.collect_net_diag(True)
check("真實環境:直連DNS有結果", all("ok" in v for v in d["direct_dns"].values()))
check("真實環境:閘道有解析", d["gateway"] is not None and "ip" in d["gateway"])
check("真實環境:NIC事件查詢可執行(大窗口)", True)
c.EVENT_WINDOW_MIN = 60 * 24 * 3
ev = c._recent_nic_events()
print("  近3天網卡/WLAN斷線事件:", ev)
check("真實環境:NIC事件查詢回傳結構", "count" in ev and "detail" in ev)

# watchdog：主流程卡死 → 留一筆 hung 紀錄並以 exit 0 結束
tmp = Path(tempfile.mkdtemp()) / "hang.jsonl"
code = (
    "import sys,time,pathlib;sys.path.insert(0,r'%s');import check_external_connectivity as c;"
    "c.LOG=pathlib.Path(r'%s');c.WATCHDOG_SECONDS=2;c.check_internet=lambda:time.sleep(60);c.main()"
    % (str(Path(__file__).resolve().parent), str(tmp))
)
t0 = time.monotonic()
r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
rec = json.loads(tmp.read_text(encoding="utf-8").splitlines()[-1]) if tmp.exists() else {}
check("watchdog:exit 0", r.returncode == 0)
check("watchdog:留下 hung 紀錄且標出卡住階段", rec.get("hung") is True and rec.get("stage") == "internet")
print("  watchdog 紀錄:", rec)

print("結果:", "全部通過" if not fails else f"失敗 {fails}")
sys.exit(1 if fails else 0)
