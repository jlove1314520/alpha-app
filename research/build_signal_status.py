"""產生 data/signal_status.json——0a節（2026-09-07總司令裁示）要求的四條新研究方向
（#49~#52）公開成績檔，含FAIL，供App將來對使用者揭露「我們測過、沒用」。

資料來源是人工核對過的紀錄摘要，不是自動剖析 HYPOTHESIS_QUEUE.md/TRIALS_LEDGER.md
（那兩份是敘事體，正則剖析容易斷章取義）。每次某條方向有新結果，就在下面
DIRECTIONS 手動新增/更新一筆，再重跑本腳本。refs 欄位可回頭查證，不接受無來源
的狀態宣告。
"""
import json
from datetime import datetime, timezone, timedelta

TAIPEI = timezone(timedelta(hours=8))

DIRECTIONS = [
    {
        "id": "49",
        "name": "隔夜 vs 日內拆解（Overnight vs Intraday Return Decomposition）",
        "status": "FAIL",
        "concluded_at": "2026-09-07",
        "summary": (
            "TAIEX(^TWII)隔夜段第1關cheap gate（TRAIN期）通過且方向與美股文獻一致，"
            "但第6關逐年一致性檢驗VAL期（2021-2024共4年）僅3/4年同號（75.0%），"
            "未達沿用#29/#34同一把尺的83.3%門檻，判FAIL結案。不泛化為「隔夜報酬"
            "異常不存在」——死的是「任意4年VAL窗口都要逐年零容錯一致」這個具體判準。"
        ),
        "refs": {
            "trials_ledger": ["#180", "#184"],
            "docs": ["HYPOTHESIS_QUEUE.md #49", "STRATEGY_GRAVEYARD.md #49"],
        },
    },
    {
        "id": "50",
        "name": "容量受限小型股（日均成交值500萬~5,000萬）",
        "status": "NOT_STARTED",
        "blocked_by": "前置資料「逐筆tick落地」尚未完成（估真實滑價需要，不用假設值）",
        "note": "事前綁定：必須小型股組顯著優於大型股組才算成立，光小型股組自己正報酬不算。",
        "refs": {"docs": ["MARATHON_PROTOCOL.md 0a節 #50"]},
    },
    {
        "id": "51",
        "name": "強制交易者事件（融券強制回補／現金增資折價／CB轉換價重設）",
        "status": "IN_PROGRESS",
        "sub_events": [
            {
                "id": "51-1",
                "name": "融券強制回補（除權息前停止過戶反推強制回補視窗）",
                "status": "FAIL",
                "concluded_at": "2026-09-07",
                "summary": (
                    "300檔樣本，1707筆可用事件。連續比例規格：TRAIN IC=+0.0192"
                    "(p=0.54)、VAL IC=-0.0373(p=0.34)，正負號不一致，null "
                    "percentile=19.0（門檻>=90.0）。追測二元規格（有無融券部位）："
                    "TRAIN diff=+0.0016、VAL diff=-0.0017，同樣正負號不一致，"
                    "null percentile=37.5，結論一致，排除「零值稀釋訊號」解讀。"
                    "兩種合理規格皆FAIL，四項事前綁定判準全數未過。反推公式本身"
                    "（PIT可得性）已驗證可行，FAIL的是「機制對報酬有無預測力」"
                    "這個獨立問題。"
                ),
                "refs": {
                    "trials_ledger": ["#186", "#189"],
                    "docs": ["HYPOTHESIS_QUEUE.md #51(h)", "STRATEGY_GRAVEYARD.md #51"],
                },
            },
            {
                "id": "51-2",
                "name": "現金增資折價（認股價折價幅度預測除權後CAR）",
                "status": "FAIL",
                "concluded_at": "2026-09-07",
                "summary": (
                    "全市場94檔曾現金增資股票，118筆事件。TRAIN IC=-0.0383"
                    "(p=0.77,n=59)、VAL IC=-0.2289(p=0.16,n=40)，同號且null "
                    "percentile=94.0（過關），但VAL Spearman p=0.1554未達0.10"
                    "顯著水準，四項判準僅顯著性一項未過，是少見「接近但未過」"
                    "的FAIL，不泛化為機制完全無效——樣本量小（n=40）可能是"
                    "檢定力問題。"
                ),
                "refs": {
                    "trials_ledger": ["#187"],
                    "docs": ["HYPOTHESIS_QUEUE.md #51(e)", "STRATEGY_GRAVEYARD.md #51"],
                },
            },
            {
                "id": "51-3",
                "name": "CB轉換價重設（MOPS重大訊息查證階段）",
                "status": "IN_PROGRESS",
                "summary": "MOPS查證三個候選方向尚在進行中，尚未產生cheap gate結果。",
                "refs": {"docs": ["HYPOTHESIS_QUEUE.md #51(d)"]},
            },
        ],
    },
    {
        "id": "52",
        "name": "事件反應速度（MOPS重大訊息T+0/T+1，依類型分群）",
        "status": "NOT_STARTED",
        "blocked_by": "前置資料「建置一.1 新聞事件管線」尚未完成，規格已寫、未跑數字",
        "refs": {"docs": ["MARATHON_PROTOCOL.md 0a節 #52"]},
    },
]


def build():
    doc = {
        "schema_version": 1,
        "generated_at": datetime.now(TAIPEI).isoformat(),
        "note": (
            "0a節（2026-09-07總司令裁示）四條新研究方向的公開成績，含FAIL——"
            "這是Alpha相對於一般籌碼工具的差異化：我們也告訴使用者「測過、沒用」。"
            "非投資建議；狀態值：NOT_STARTED/IN_PROGRESS/FAIL/EXPERIMENTAL/PASS。"
        ),
        "directions": DIRECTIONS,
    }
    out_path = "../data/signal_status.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"寫入 {out_path}，共 {len(DIRECTIONS)} 條方向")


if __name__ == "__main__":
    build()
