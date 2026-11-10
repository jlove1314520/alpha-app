# -*- coding: utf-8 -*-
"""先.一五八-2（收件匣 042 B）自測：DevQueue 維運比重上限。不碰真檔（佇列與狀態檔都改指到暫存資料夾）。
1. 分類：[維運]／冒煙 → 維運；[研究]／標題含紙上 → 研究；其他 → 開發；P0（資料錯／停擺／真錢）認得出來。
2. [自走補入] 的非 P0 維運條目只記不派（跳過）；P0 的照派。
3. 連續 2 輪派維運 → 第 3 輪跳過排在前面的維運，改派研究條目；派完研究，下一輪維運又可以派。
4. 連續 2 輪維運、但佇列沒有研究／紙上 → 放行維運（不空轉）。
5. 自身失敗 fail open：狀態檔壞掉照樣回傳原本結果。
跑法：python scripts/selftest_dev_queue_maint_cap.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

import dev_queue_runner as D  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(f"{'OK  ' if ok else 'FAIL'} {name} {detail}")
    if not ok:
        fails.append(name)


tmp = Path(tempfile.mkdtemp())
D.QUEUE = tmp / "PENDING_QUEUE.md"
D.STATE = tmp / "state.json"

M1 = "- [ ] **甲.1 冒煙 #12 偶發 FAIL** [維運]（DevQueue 可執行）"
M2 = "- [ ] **甲.2 排程心跳核對** [維運]（DevQueue 可執行）"
AF = "- [ ] **甲.0 PROGRESS 格式整理** [維運]（DevQueue 可執行；[自走補入] 來源：BACKLOG）"
P0 = "- [ ] **甲.9 market.yml 停擺 3 小時** [維運]（DevQueue 可執行；[自走補入] 來源：看門狗）"
R1 = "- [ ] **乙.1 墓園重審第三批** [研究]（DevQueue 可執行）"
PP = "- [ ] **乙.2 F7 每日產生器上紙上** [開發]（DevQueue 可執行）"
DV = "- [ ] **丙.1 自選股排序按鈕** [開發]（DevQueue 可執行）"


def write(*rows):
    D.QUEUE.write_text("# 佇列\n\n" + "\n".join(rows) + "\n", encoding="utf-8")


def nxt():
    r = D.find_next()
    return D.item_key(r[1]) if r else None


def set_hats(h):
    st = D._load_state()
    st["_recent_hats"] = h
    st["_last_was_batch"] = False
    D._save_state(st)


# 1
write(M1)
check("1 冒煙→維運", D.item_hat(M1) == "維運")
check("1 [研究]→研究", D.item_hat(R1) == "研究")
check("1 標題含紙上→研究", D.item_hat(PP) == "研究")
check("1 一般開發→開發", D.item_hat(DV) == "開發")
check("1 停擺＝P0", D.is_p0(P0) and not D.is_p0(M1))

# 2
set_hats([])
write(AF, M1, R1)
check("2 [自走補入] 非 P0 維運跳過", nxt() == "甲.1 冒煙 #12 偶發 FAIL", str(nxt()))
write(P0, M1)
check("2 [自走補入] 的 P0 照派", nxt() == "甲.9 market.yml 停擺 3 小時", str(nxt()))
write(AF)
check("2 只剩 [自走補入] 維運 → 不派", nxt() is None, str(nxt()))

# 3
write(M1, M2, R1, DV)
set_hats(["研究", "維運"])
check("3 只連 1 輪維運 → 照順序派維運", nxt() == "甲.1 冒煙 #12 偶發 FAIL")
D._note_dispatch(M1)
check("3 記帽子", D._load_state()["_recent_hats"][-2:] == ["維運", "維運"])
check("3 連 2 輪維運 → 第 3 輪改派研究", nxt() == "乙.1 墓園重審第三批", str(nxt()))
D._note_dispatch(R1)
check("3 派完研究，維運可以再派", nxt() == "甲.1 冒煙 #12 偶發 FAIL")
write(M1, M2, PP)
set_hats(["維運", "維運"])
check("3 紙上產生器也算研究", nxt() == "乙.2 F7 每日產生器上紙上", str(nxt()))

# 4
write(M1, M2, DV)
set_hats(["維運", "維運"])
check("4 沒有研究可派 → 放行維運不空轉", nxt() == "甲.1 冒煙 #12 偶發 FAIL", str(nxt()))

# 5
D.STATE.write_text("{壞掉", encoding="utf-8")
write(M1, R1)
check("5 狀態檔壞掉照常回傳", nxt() == "甲.1 冒煙 #12 偶發 FAIL", str(nxt()))
D.MAINT_CAP_ON = False
set_hats(["維運", "維運"])
check("5 關掉開關＝舊行為", nxt() == "甲.1 冒煙 #12 偶發 FAIL")

print("\n結果：" + ("全部通過" if not fails else f"FAIL {len(fails)} 項：{fails}"))
sys.exit(1 if fails else 0)
