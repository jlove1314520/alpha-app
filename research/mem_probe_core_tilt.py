"""稽核.六(a) core_tilt_backtest：以暫存輸出路徑跑完整 main()（不覆蓋研究輸出檔），
執行緒每2秒取樣 private memory 記峰值，並印出各階段。"""
import sys, threading, time, json, tempfile, pathlib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
exec(open("mem_probe_factor_ic.py", encoding="utf-8").read().split("import factor_ic as F")[0])
import core_tilt_backtest as C
C.OUT_JSON = pathlib.Path(tempfile.gettempdir()) / "core_tilt_probe_out.json"
peak = [0.0]; stop = [False]
def sampler():
    while not stop[0]:
        peak[0] = max(peak[0], private_mb()); time.sleep(2)
th = threading.Thread(target=sampler, daemon=True); th.start()
t0 = time.time(); print("baseline", round(private_mb()), flush=True)
try:
    C.main()
finally:
    stop[0] = True
    rec = {"peak_private_mb": round(peak[0]), "final_private_mb": round(private_mb()), "sec": round(time.time()-t0)}
    print("MEMPROBE", rec, flush=True)
    json.dump(rec, open("mem_probe_core_tilt.json", "w"))
