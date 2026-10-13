# -*- coding: utf-8 -*-
"""先.八十二-12（2026-10-13）：手機版面回歸比對自測（假截圖＋假版面，不開瀏覽器、不送推播）。
① 第一次跑（沒有前一版）→ 不報  ② 跟前一版一樣 → 不報  ③ 卡片寬度差 >8px → 報  ④ 新出現橫向溢出 → 報
⑤ 第一屏大片變樣（>40%）→ 報  ⑥ 小幅資料變動（<40%）→ 不報  ⑦ 有差異才推播、內容含頁名
用法：python scripts/selftest_phone_regression.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image  # noqa: E402
import phone_regression as R  # noqa: E402

tmp = Path(tempfile.mkdtemp())
a, b = tmp / "a", tmp / "b"
a.mkdir(); b.mkdir()


def img(p, box=None):
    im = Image.new("L", (390, 844), 20)
    if box:
        im.paste(230, box)
    im.save(p)


def lay(**over):
    base = {"overflow_px": 0, "cards": [{"key": "c1", "x": 16, "w": 358}, {"key": "c2", "x": 16, "w": 358}], "png": "home.png"}
    base.update(over)
    return {"home": base}


R.PAGES = ["home"]
img(a / "home.png"); img(b / "home.png")
res = [("②一樣→不報", R.compare(lay(), lay(), a, b) == [])]
res.append(("③卡片寬度差 20px→報", len(R.compare(lay(cards=[{"key": "c1", "x": 16, "w": 338}, {"key": "c2", "x": 16, "w": 358}]), lay(), a, b)) == 1))
res.append(("④新出現橫向溢出→報", "橫向溢出" in R.compare(lay(overflow_px=24), lay(), a, b)[0]["detail"]))
img(a / "home.png", (0, 0, 390, 600))
res.append(("⑤第一屏大片變樣→報", "明顯變樣" in (R.compare(lay(), lay(), a, b) or [{"detail": ""}])[0]["detail"]))
img(a / "home.png", (0, 0, 390, 120))
res.append(("⑥小幅變動（約 14%）→不報", R.compare(lay(), lay(), a, b) == []))
R.OUT = tmp / "out"
pushed = []


def fake_capture(url, day_dir, over=None):
    img(day_dir / "home.png")
    return lay(**(over or {}))


r1 = R.main(["--url", "x"], push=lambda t, bd: (pushed.append((t, bd)), {"ok": 1})[1], capture_fn=fake_capture)
res.append(("①第一次跑沒有前一版→不報", r1["issues"] == [] and r1["baseline"] is None and not pushed))
prev = R.OUT / "2000-01-01"; prev.mkdir()
(prev / "layout.json").write_text(json.dumps(lay()), encoding="utf-8"); img(prev / "home.png")
r2 = R.main(["--url", "x"], push=lambda t, bd: (pushed.append((t, bd)), {"ok": 1})[1],
            capture_fn=lambda u, d: fake_capture(u, d, {"overflow_px": 30}))
res.append(("⑦有差異才推播、內容含頁名", r2["baseline"] == "2000-01-01" and len(pushed) == 1 and "home" in pushed[0][1] and "1 頁" in pushed[0][0]))
for n, ok in res:
    print(("PASS " if ok else "FAIL ") + n)
bad = sum(1 for _, ok in res if not ok)
print(f"合計 {len(res)} 項，失敗 {bad}")
sys.exit(1 if bad else 0)
