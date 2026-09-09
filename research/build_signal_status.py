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
        "name": "強制交易者事件（台股：融券強制回補／現金增資折價／CB轉換價重設；美股：S&P指數成分調整）",
        "status": "FAIL",
        "concluded_at": "2026-09-09",
        "summary": (
            "台股三個子事件（強制回補、現金增資折價、CB轉換價重設）與美股S&P指數"
            "Addition子測試皆FAIL，#51正式結案（美股Deletion子測試因下市股價格污染雷"
            "事前排除未測，非跳關）。不泛化為「事前已知日期的結構性交易者」這個機制"
            "大類完全無效——四個已測子事件涵蓋四種不同觸發事件＋四種不同構造，共同點"
            "僅止於經濟理由的抽象類比，不代表機制類別本身被推翻。"
        ),
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
                "name": "CB轉換價重設（轉換價格調整幅度預測forward報酬）",
                "status": "FAIL",
                "concluded_at": "2026-09-07",
                "summary": (
                    "MOPS轉換公司債公告彙總表查證確認資料可行（2市場×15民國年，"
                    "3078筆窗口+重設幅度皆可用事件）。事前綁定假設：重設幅度"
                    "（向下調整幅度）越大，生效日後20交易日CAR應越負。結果："
                    "TRAIN IC=+0.0117(p=0.60,n=2031)、VAL IC=+0.0430(p=0.16,n=1047)，"
                    "train/val同號但方向與事前綁定的負相關預期相反，VAL洗牌null"
                    "percentile=8.0遠低於90.0門檻（且遠低於50，代表真實訊號比多數"
                    "隨機打亂還更偏離假設方向）。四項判準僅同號成立，其餘全數未過，"
                    "判FAIL。不泛化為「可轉債轉換價格重設機制完全無效」——只測了"
                    "單一固定20交易日窗口+向下重設半邊，未測向上重設/不同窗口長度。"
                ),
                "refs": {
                    "trials_ledger": ["#190"],
                    "docs": ["HYPOTHESIS_QUEUE.md #51(i)", "STRATEGY_GRAVEYARD.md #51"],
                },
            },
            {
                "id": "51-us",
                "name": "美股 S&P 指數成分調整（Addition事件公告日→生效日CAR搶跑漲幅）",
                "status": "FAIL",
                "concluded_at": "2026-09-09",
                "summary": (
                    "僅測Addition（事前排除Deletion，避開被收購/破產下市股在yfinance"
                    "低覆蓋率下的價格污染雷）。222筆可用事件，價格源改用yfinance原生"
                    "美股資料（非違規的FinMind USStockPrice）。控制組own_ticker_window/"
                    "cross_ticker_window兩變體各N=200：TRAIN（2012-2020,n=25）"
                    "mean_CAR=+11.59%嚴格大於控制組最大值（CHEAP_PASS，但樣本量過小）；"
                    "VAL（2021-2024,n=197）mean_CAR=+1.56%，百分位97.8但未嚴格大於"
                    "控制組最大值2.38%（FAIL）。方向與index-effect文獻一致，是"
                    "「近年套利搶跑減弱」已知風險下的誠實邊緣FAIL，非管線問題。"
                ),
                "refs": {
                    "trials_ledger": ["#222"],
                    "docs": ["HYPOTHESIS_QUEUE.md #51-US", "US_LEADS.md #32"],
                },
            },
        ],
    },
    {
        "id": "52",
        "name": "事件反應速度（重大申報/訊息 T+0/T+1，依類型分群，台美股分開跑）",
        "status": "FAIL",
        "concluded_at": "2026-09-09",
        "note": "台股(MOPS)與美股(SEC EDGAR)是同一個經濟假說在兩個市場各自的資料源，各自獨立判定，本輪兩者皆已結案，母層狀態依兩子事件皆FAIL標記FAIL。",
        "sub_events": [
            {
                "id": "52-tw",
                "name": "台股 MOPS 重大訊息",
                "status": "FAIL",
                "concluded_at": "2026-09-09",
                "summary": (
                    "gate1（CAR事件研究，4類CHEAP_PASS：併購/增減資/財務/人事，"
                    "control_percentile皆100.0，訊號嚴格大於全部400次控制組抽樣"
                    "最大值）證實這4類重大訊息公告確實觸發顯著大於隨機的異常反應"
                    "幅度。但gate2（PEAD式方向性延續檢定，看到reaction_day+1初始"
                    "反應方向後，接下來H=5交易日是否有可預測的同向延續）4類全數"
                    "FAIL：併購signal=0.0052<control_max=0.0112(percentile=94.5)、"
                    "增減資signal=0.0000<control_max=0.0036(percentile=35.0)、"
                    "財務signal=0.0020<control_max=0.0022(percentile=98.5)、"
                    "人事signal=0.0018<control_max=0.0030(percentile=97.75)。"
                    "正式結論：異常反應存在但不可交易（已price-in、無延續）。"
                    "不泛化為「重大訊息公告完全無效」——只測了H=5單一窗口的"
                    "方向性延續假設，未測其他horizon（H=1/3/10）或反轉假設"
                    "（over-reaction後是否存在反轉，經濟理由與延續假設相反，"
                    "屬另一條獨立假設，未來若重探此方向應優先測反轉）。"
                ),
                "refs": {
                    "trials_ledger": ["#221", "#223"],
                    "docs": ["HYPOTHESIS_QUEUE.md #52 (x)", "STRATEGY_GRAVEYARD.md #52"],
                },
            },
            {
                "id": "52-us",
                "name": "美股 SEC EDGAR 8-K 事件反應速度",
                "status": "FAIL",
                "concluded_at": "2026-09-08",
                "summary": (
                    "測過三個item family：Item 2.02（排程財報PEAD）、Item 5.02（非排程"
                    "主管異動）、Item 1.01（非排程重大協議）——涵蓋排程性/非排程負面/"
                    "非排程正中性三種不同性質的揭露，皆用同一套PIT錨點(acceptanceDateTime)"
                    "/反應日對齊/配對式控制組機制測試，全部FAIL。2.02兩期方向一致但量級"
                    "不足（TRAIN百分位62.5/VAL 83.5）；5.02 TRAIN幾乎等於隨機、VAL反向"
                    "（百分位55.0/8.0）；1.01兩期皆低於控制組平均（百分位36.0/43.0），"
                    "是三者中最乾淨的無edge結果。已足以支持整體無edge結論，不再測第四個"
                    "item family。"
                ),
                "refs": {
                    "trials_ledger": ["#215", "#216", "#217", "#218", "#220"],
                    "docs": ["HYPOTHESIS_QUEUE.md #52-US", "STRATEGY_GRAVEYARD.md #52-US", "US_LEADS.md #29-31"],
                },
            },
        ],
        "refs": {"docs": ["MARATHON_PROTOCOL.md 0a節 #52"]},
    },
    {
        "id": "62",
        "name": "鉅額逐筆交易（Block Trade，配對交易子集）跟隨訊號——資訊不對稱/知情大額交易類",
        "status": "FAIL",
        "concluded_at": "2026-09-09",
        "note": (
            "非0a節四條方向之一（屬HYPOTHESIS_QUEUE.md第⑫類「知情大額交易跟隨」機制），"
            "round475已直接寫入本檔公開，本輪一併沿用避免遺失。"
        ),
        "summary": (
            "事前假設賣方發起鉅額配對交易後有賣壓延續（資訊不對稱下知情交易者領先"
            "市場），VAL期(2021-2024)n_val=237筆事件（N=5/10/20交易日三個窗口皆同），"
            "三個窗口方向一致朝反方向、百分位皆<10（非邊緣case），FAIL。研判賣方較"
            "可能是機構調節部位或反映流動性溢價而非知情交易。"
        ),
        "refs": {
            "trials_ledger": ["#224"],
            "docs": ["HYPOTHESIS_QUEUE.md #62", "STRATEGY_GRAVEYARD.md #62", "TW_LEADS.md #16"],
        },
    },
    {
        "id": "63",
        "name": "借券費率異常飆升作為知情放空訊號（台股）",
        "status": "FAIL",
        "concluded_at": "2026-09-09",
        "note": (
            "非0a節四條方向之一（屬HYPOTHESIS_QUEUE.md第⑫類「借券費率知情放空」"
            "機制），比照#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "第1關cheap gate（三N值percentile皆100.0）跟第2關參數高原"
            "（Z_THRESH∈{1.5,2.0,2.5,3.0}共12組全PASS）都乾淨通過，敗在第4關"
            "成本敏感度：round-trip成本1x下N5/N10已轉負、N20勉強為正但2x/3x"
            "皆轉負，三個N值沒有一個能在2x成本下存活。不泛化為「借券市場定價"
            "機制無效」——統計顯著性乾淨，死因是本次事前綁定的應用方式（單次"
            "降曝險而非實際放空）絕對報酬幅度不足以覆蓋成本，不是方向錯或雜訊。"
        ),
        "refs": {
            "trials_ledger": ["#225", "#226", "#227"],
            "docs": ["HYPOTHESIS_QUEUE.md #63", "STRATEGY_GRAVEYARD.md f_lending_fee_spike"],
        },
    },
    {
        "id": "64",
        "name": "台指期貨基差regime訊號預測TAIEX現貨報酬",
        "status": "FAIL",
        "concluded_at": "2026-09-09",
        "note": (
            "非0a節四條方向之一（期貨軌「除非有全新機制假說」例外條款觸發，"
            "屬HYPOTHESIS_QUEUE.md第⑬類「期貨定價期限結構」機制），比照#62"
            "先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "訊號=sign(basis相對60日trailing均值偏離)逐日換倉，目標=TAIEX現貨"
            "次日報酬，全歷史(2000-2024,n=6125)累積+314.3%，但用2026-09-07"
            "升級後的新版控制組標準（嚴格贏過控制組抽樣最大值，非90百分位）"
            "檢定，合併400次抽樣percentile=97.0仍未過關（block_shuffle_20d"
            "變體最大值12.2143高於真實訊號4.1425），FAIL。不泛化為「basis對"
            "TAIEX現貨完全無預測力」——只代表本次具體規格（60日窗/逐日換倉）"
            "不夠格，也是新控制組標準上線後第一個「舊標準會誤判過關」的實例。"
        ),
        "refs": {
            "trials_ledger": ["#228"],
            "docs": ["HYPOTHESIS_QUEUE.md #64", "STRATEGY_GRAVEYARD.md fut_basis_regime_gate64", "FUT_LEADS.md #29"],
        },
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
