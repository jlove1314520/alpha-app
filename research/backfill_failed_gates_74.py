# backfill_failed_gates_74.py — 總司令裁示【研究層·#74續：先證明量尺是對的，再談關卡】
# 第3點(b)：回頭從TRIALS_REGISTRY.jsonl自身的result/notes文字考據47筆FAIL各自死在
# 哪一關，考據不出來的誠實標unknown，不用推測填。
#
# **為什麼不直接改寫TRIALS_REGISTRY.jsonl的歷史列**：trial_registry.py模組docstring
# 明寫「這支不會去改寫既有的歷史列（那是append-only的歷史證據，改了就毀了）」。
# 這裡比照同一個append-only精神，輸出一份獨立的「補登記」檔
# research/TRIALS_FAILED_GATES_BACKFILL.jsonl，每筆用`amends_id`指回原始編號，
# 不動原始58筆本身一個字。
#
# **分類方法**：不用「gate\d」子字串比對（會被"fut_settlement_event_gate60_pre"
# 這種把候選編號#60直接放進檔名的命名法誤判成「GATE6」——這是查證過程中真的
# 踩到的陷阱，見PROGRESS.md/本輪commit說明），改成逐筆讀result+notes的完整中文
# 敘述人工判讀，只有明確、無歧義的關卡語彙才分類，判不準一律unknown。
#
# 值域（見trial_registry.py::FAILED_GATES_VOCAB，本檔另外多用兩個本地類別，
# 因為總司令要的是「考據結果」不是「硬塞進六關」——這兩類是真的查得到死因、
# 只是死因不屬於GATE_SEQUENCE六關本身，標unknown反而不誠實）：
#   gate1~gate6              = 正式GATE_SEQUENCE六關（sanity/隨機控制組/參數高原/
#                               成本敏感度/leave-one-out/逐年一致性）
#   cheap_gate_precheck       = 六關之前的「樣本數/同號/方向/null percentile」四項
#                               合併篩選（hypothesis_queue多數FAIL卡在這裡，
#                               不等於正式GATE1 sanity）
#   universe_contamination_check = 美股宇宙已知死亡螺旋股污染做空腿的資料完整性
#                               複查，不是策略邏輯關卡
#   other_protocol            = 候選用自己的多條件協定（例如regime overlay的
#                               MDD縮小/危機視窗/參數高原五點協定），跟六關不是
#                               同一套框架
#   unknown                   = 讀完result+notes仍無法確定，誠實標記

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=8))
JSONL = Path(__file__).parent / "TRIALS_REGISTRY.jsonl"
OUT = Path(__file__).parent / "TRIALS_FAILED_GATES_BACKFILL.jsonl"

# 人工逐筆判讀結果（見本輪對話紀錄逐筆引用的原文依據，此處只留結論+一句話理由，
# 完整原文引用在PROGRESS.md/commit說明裡，不在這裡重複整份result/notes）。
CLASSIFICATION: dict[int, tuple[str, str]] = {
    187: ("cheap_gate_precheck", "候選名稱與notes明寫「第1關cheap gate」「四項事前綁定判準」"),
    189: ("cheap_gate_precheck", "候選名稱明寫「第1關cheap gate」，notes「四個事前綁定判準」"),
    190: ("cheap_gate_precheck", "notes明寫「第1關cheap gate。四項判準」"),
    193: ("universe_contamination_check", "US死亡螺旋股污染做空腿複查，非GATE_SEQUENCE"),
    194: ("gate2", "候選名稱與result明寫「GATE_SEQUENCE第2關隨機控制組」"),
    195: ("gate1", "候選名稱明寫「第1關sanity」，sanity2/sanity3方向反轉未進入第2關"),
    196: ("universe_contamination_check", "US死亡螺旋股污染做空腿複查，非GATE_SEQUENCE"),
    197: ("universe_contamination_check", "US死亡螺旋股污染做空腿複查，非GATE_SEQUENCE"),
    198: ("gate1", "與#54(195)同一批sanity1/2/3篩選，notes明寫「未進GATE_SEQUENCE第2關」"),
    199: ("universe_contamination_check", "US死亡螺旋股污染做空腿複查（25檔擴大版），非GATE_SEQUENCE"),
    200: ("universe_contamination_check", "US死亡螺旋股污染做空腿複查（25檔擴大版），非GATE_SEQUENCE"),
    201: ("gate2", "notes明寫「GATE_SEQUENCE第2關隨機控制組。第1關sanity三項皆PASS」"),
    202: ("gate2", "候選名稱與notes明寫「GATE_SEQUENCE第2關隨機控制組」「死於第2關」"),
    203: ("cheap_gate_precheck", "US因子IC對null percentile門檻篩選（bonferroni_n門檻），非六關"),
    204: ("cheap_gate_precheck", "同上，同批us_factor_ic_by_size.py附帶產出"),
    205: ("cheap_gate_precheck", "同上"),
    207: ("cheap_gate_precheck", "同上"),
    208: ("cheap_gate_precheck", "同上"),
    209: ("gate2", "notes明寫「新版control_group_standard要求嚴格贏過控制組最大值」"),
    212: ("gate4", "候選名稱明寫「GATE4 成本敏感度」，TRAIN 1x即轉負"),
    213: ("cheap_gate_precheck", "事件研究對500次隨機窗口percentile篩選，非正式六關"),
    214: ("cheap_gate_precheck", "同上"),
    215: ("cheap_gate_precheck", "候選名稱明寫「cheap gate 小樣本先導」"),
    216: ("cheap_gate_precheck", "同上（VAL期）"),
    217: ("cheap_gate_precheck", "候選名稱明寫「cheap gate 小樣本先導」"),
    218: ("cheap_gate_precheck", "同上（VAL期）"),
    219: ("cheap_gate_precheck", "事件研究null percentile+同號兩項判準，非正式六關"),
    220: ("cheap_gate_precheck", "事件研究signal vs control_max百分位篩選，非正式六關"),
    222: ("cheap_gate_precheck", "事件研究CAR vs 控制組最大值百分位篩選，非正式六關"),
    223: ("cheap_gate_precheck", "notes內「gate1/gate2」為候選#52自訂的兩階段內部測試"
                                   "（反應幅度/延續性），非GATE_SEQUENCE正式編號，判為此類避免誤讀"),
    224: ("cheap_gate_precheck", "訊號percentile vs控制組平均/最大值篩選，非正式六關"),
    227: ("gate4", "候選名稱明寫「gate4成本敏感度」，notes「gate1/gate2 PASS但gate4不過」"),
    228: ("cheap_gate_precheck", "control_percentile vs控制組最大值篩選（2026-09-07標準），非正式六關"),
    229: ("cheap_gate_precheck", "notes明寫「cheap IC gate未過」"),
    230: ("cheap_gate_precheck", "4項判準(TRAIN/VAL x 兩窗口)百分位篩選，非正式六關"),
    232: ("gate2", "result明寫「屬GATE_SEQUENCE第2關隨機控制組決定性未過」"),
    233: ("cheap_gate_precheck", "候選名稱明寫「第1關cheap IC gate」"),
    234: ("cheap_gate_precheck", "notes明寫「cheap gate不計成本」（FUT趨勢跟隨家族）"),
    235: ("cheap_gate_precheck", "同上"),
    236: ("cheap_gate_precheck", "同上"),
    237: ("cheap_gate_precheck", "同上"),
    238: ("cheap_gate_precheck", "同上"),
    239: ("cheap_gate_precheck", "notes明寫「第1關cheap gate四項判準」"),
    241: ("cheap_gate_precheck", "候選名稱明寫「option_skew_cheap_gate」"),
    242: ("gate2", "notes明寫在測#53於GATE_SEQUENCE第2關（控制組最大值）前的引擎修正"),
    243: ("other_protocol", "regime overlay自訂MDD縮小/危機視窗/參數高原五點協定，非GATE_SEQUENCE"),
    244: ("other_protocol", "同上，FUT軌配合版"),
}


def main() -> None:
    recs = [json.loads(l) for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    fails = [r for r in recs if r.get("verdict") == "FAIL"]
    fail_ids = {r["id"] for r in fails}

    missing = fail_ids - set(CLASSIFICATION)
    extra = set(CLASSIFICATION) - fail_ids
    if missing:
        raise SystemExit(f"分類表漏了這些FAIL編號，不得補登：{sorted(missing)}")
    if extra:
        raise SystemExit(f"分類表多出不是FAIL（或不存在）的編號，不得補登：{sorted(extra)}")

    now = datetime.now(TZ).isoformat(timespec="seconds")
    lines = []
    for tid in sorted(CLASSIFICATION):
        gate, evidence = CLASSIFICATION[tid]
        lines.append(json.dumps({
            "amends_id": tid,
            "failed_gates": [gate],
            "evidence": evidence,
            "method": "人工逐筆讀TRIALS_REGISTRY.jsonl該筆result+notes原文判讀，"
                      "不用gate\\d子字串比對（會被候選編號如#60誤判成GATE6）",
            "backfilled_at": now,
            "backfilled_by": "trial_registry.register_trial() 未涵蓋——append-only補登記，"
                              "不改寫TRIALS_REGISTRY.jsonl本身",
        }, ensure_ascii=False))

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    from collections import Counter
    dist = Counter(g for g, _ in CLASSIFICATION.values())
    print(f"補登 {len(CLASSIFICATION)} 筆，寫入 {OUT.name}")
    print("分布：", dict(dist))
    print(f"\n關鍵結論：47筆FAIL裡，明確卡在正式GATE_SEQUENCE gate5(leave-one-out)"
          f"或gate6(逐年一致性)的筆數 = "
          f"{sum(1 for g,_ in CLASSIFICATION.values() if g in ('gate5','gate6'))}")


if __name__ == "__main__":
    main()
