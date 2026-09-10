"""產生 data/signal_status.json——0a節（2026-09-07總司令裁示）要求的四條新研究方向
（#49~#52）公開成績檔，含FAIL，供App將來對使用者揭露「我們測過、沒用」。實務上已
擴及所有hypothesis_queue後續編號假說（#53起，比照#62先例），只要已在
STRATEGY_GRAVEYARD.md/TRIALS_LEDGER.md正式結案即納入，不限於原始四條方向本身。

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
        "id": "53",
        "name": "全市場報酬離散度速度（Cross-Sectional Return Dispersion Velocity，regime overlay）",
        "status": "FAIL",
        "concluded_at": "2026-09-08",
        "note": (
            "非0a節四條方向之一（屬「市場總開關假設軸」regime overlay家族第1個"
            "成員），比照#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "截面報酬離散度異常偏高時降曝險（連續縮放）。第1關sanity通過，但"
            "第2關隨機控制組（3變體N=100）：level/vel兩規格、TRAIN/VAL兩期共4項"
            "判定全數未嚴格贏過控制組最大值（62~73百分位不算通過），FAIL。不"
            "泛化為離散度訊號不存在——死的是f(z)=1-z這個固定線性映射建構。"
        ),
        "refs": {
            "trials_ledger": ["#192", "#194"],
            "docs": ["HYPOTHESIS_QUEUE.md #53", "STRATEGY_GRAVEYARD.md #53"],
        },
    },
    {
        "id": "54",
        "name": "成交值集中度速度（Turnover Concentration Velocity，regime overlay）",
        "status": "FAIL",
        "concluded_at": "2026-09-08",
        "note": (
            "非0a節四條方向之一（屬「市場總開關假設軸」regime overlay家族第2個"
            "成員），比照#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "逐檔成交值占比HHI異常偏升時降曝險。第1關sanity兩項獨立檢定方向"
            "皆與事前綁定相反（危機窗口僅1/3命中；高集中度組前瞻報酬反而"
            "高於低集中度組），未進第2關即判FAIL。可能反映權值股領漲的多頭"
            "慣性延續，而非參與面收窄的risk-off訊號，方向與原假設相反。"
        ),
        "refs": {
            "trials_ledger": ["#195"],
            "docs": ["HYPOTHESIS_QUEUE.md #54", "STRATEGY_GRAVEYARD.md #54"],
        },
    },
    {
        "id": "55",
        "name": "三大法人買賣超截面離散度速度（Institutional Flow Dispersion Velocity，regime overlay）",
        "status": "FAIL",
        "concluded_at": "2026-09-08",
        "note": (
            "非0a節四條方向之一（屬「市場總開關假設軸」regime overlay家族第3個"
            "成員），比照#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "法人淨買超規模標準化後取截面標準差，異常偏升時降曝險。sanity1/2"
            "皆PASS，但sanity3（tertile條件式前瞻報酬方向）level/vel兩版皆與"
            "事前綁定方向相反，未進第2關即判FAIL。與#43（買賣超集中度HHI，"
            "已FAIL）方向一致：法人資金集中在台股歷史樣本上系統性不是"
            "risk-off訊號。"
        ),
        "refs": {
            "trials_ledger": ["#198"],
            "docs": ["HYPOTHESIS_QUEUE.md #55", "STRATEGY_GRAVEYARD.md #55"],
        },
    },
    {
        "id": "57",
        "name": "全市場當沖比重截面離散度速度（Day-Trading Ratio Dispersion Velocity，regime overlay）",
        "status": "FAIL",
        "concluded_at": "2026-09-08",
        "note": (
            "非0a節四條方向之一（屬「市場總開關假設軸」regime overlay家族第4個"
            "成員，#53～#57家族至此0勝5敗結案，#56撤案不計入），比照#62先例"
            "一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "逐檔當沖成交值占比取截面標準差，異常偏升時降曝險。第1關sanity"
            "三項皆PASS，但第2關隨機控制組（同#53框架）：level/vel兩規格、"
            "TRAIN/VAL兩期共4項判定全數未嚴格贏過控制組最大值（44~99百分位"
            "皆不算通過），FAIL，死法跟#53完全相同。"
        ),
        "refs": {
            "trials_ledger": ["#201"],
            "docs": ["HYPOTHESIS_QUEUE.md #57", "STRATEGY_GRAVEYARD.md #57"],
        },
    },
    {
        "id": "58",
        "name": "反向波動度加權投資組合建構（Inverse-Volatility-Weighted Portfolio Construction）",
        "status": "FAIL",
        "concluded_at": "2026-09-08",
        "note": (
            "非0a節四條方向之一（屬「投資組合建構」機制家族第1個成員），比照"
            "#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "以trailing 60日波動度倒數加權、月頻再平衡，vs等權buy-and-hold。"
            "第1關sanity、TRAIN期控制組檢定皆PASS，但VAL期未嚴格贏過控制組"
            "抽樣最大值（百分位99.0，邊緣FAIL）。不泛化為風險平價機制無效——"
            "毛報酬方向正確，死的是VAL期邊際優勢小到跟隨機權重分配幾乎"
            "無法區分。"
        ),
        "refs": {
            "trials_ledger": ["#202"],
            "docs": ["HYPOTHESIS_QUEUE.md #58", "STRATEGY_GRAVEYARD.md #58"],
        },
    },
    {
        "id": "59",
        "name": "最小變異數投資組合建構（Minimum-Variance Portfolio Construction，共變異數矩陣版）",
        "status": "FAIL",
        "concluded_at": "2026-09-08",
        "note": (
            "非0a節四條方向之一（屬「投資組合建構」機制家族第2個成員），比照"
            "#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "Ledoit-Wolf收縮估計共變異數矩陣、全域最小變異數封閉解、月頻"
            "再平衡。前3關（sanity/控制組/參數高原）全部乾淨通過，敗在第4關"
            "成本敏感度：換手率約為#58固定拉回版本的6.3倍，1x成本下TRAIN期"
            "淨溢酬已轉負。不泛化為共變異數結構分散化效益不存在——死的是"
            "封閉解求解帶來的高換手成本吃光毛報酬優勢。"
        ),
        "refs": {
            "trials_ledger": ["#212"],
            "docs": ["HYPOTHESIS_QUEUE.md #59", "STRATEGY_GRAVEYARD.md #59"],
        },
    },
    {
        "id": "60",
        "name": "台指選擇權/期貨結算到期日機械性效應（Derivatives Settlement/Expiration Mechanical Effect）",
        "status": "FAIL",
        "concluded_at": "2026-09-08",
        "note": (
            "非0a節四條方向之一（屬「衍生性商品結算機械性效應」機制，該大類"
            "至此0勝1敗結案），比照#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "TAIFEX台指期貨月合約結算日前後事件研究，事前綁定PRE_WINDOW=3/"
            "POST_WINDOW=1。結算前3日報酬train/val正負號不一致；結算當日"
            "報酬TRAIN顯著但VAL不顯著（百分位47.6），判定為noise，兩子測試"
            "皆FAIL。只測了一組事前綁定的單點，未掃描其他窗口組合。"
        ),
        "refs": {
            "trials_ledger": ["#213", "#214"],
            "docs": ["HYPOTHESIS_QUEUE.md #60", "STRATEGY_GRAVEYARD.md #60"],
        },
    },
    {
        "id": "61",
        "name": "央行理監事會議決策事件（重貼現率變動）",
        "status": "FAIL",
        "concluded_at": "2026-09-08",
        "note": (
            "非0a節四條方向之一（屬HYPOTHESIS_QUEUE.md第⑩類「央行政策決策事件」"
            "機制），比照#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "訊號=重貼現率變動事件後TAIEX後續報酬，第1關cheap gate：TRAIN"
            "(2018-2020,12場)mean=-0.6541%(p=0.2128)、VAL(2021-2024,16場)"
            "mean=+0.5263%(p=0.0991)，train/val正負號不一致（TRAIN負VAL正），"
            "即使VAL單獨對500次隨機交易日null的雙尾percentile=93.6過90.0門檻，"
            "依同一把尺（#60判例）train/val方向不一致即整體FAIL。事前綁定子測試1"
            "不過關即快殺，未再測子測試2（決策方向分組，樣本量極小僅11筆）。"
        ),
        "refs": {
            "trials_ledger": ["#219"],
            "docs": ["HYPOTHESIS_QUEUE.md #61", "STRATEGY_GRAVEYARD.md #61", "TW_LEADS.md #15"],
        },
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
    {
        "id": "65",
        "name": "產業龍頭股跨期領先-落後動能（Hou 2007資訊擴散機制）",
        "status": "FAIL",
        "concluded_at": "2026-09-09",
        "note": (
            "非0a節四條方向之一（屬HYPOTHESIS_QUEUE.md第⑭類「同產業龍頭-族群"
            "資訊擴散延遲」機制，經濟機制與已FAIL的#11同期橫斷面相對強度明確"
            "不同），比照#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "300檔樣本、依trailing 20日均成交金額分產業選龍頭，龍頭t期5日報酬"
            "廣播給族群成員、預測族群成員t+1期5日報酬。TRAIN mean_ic=+0.0072/"
            "IR=+0.065(n=288日)、VAL mean_ic=+0.0094/IR=+0.091/hit_rate=0.51"
            "(n=193日)，train/val同號（符合事前綁定方向）但VAL |IC|遠小於"
            "事前訂的0.02門檻，且null_percentile=87.5未過90.0，FAIL。不泛化"
            "為「同產業龍頭-族群資訊擴散延遲」機制完全不存在——只測了「成交"
            "金額最大」當關注度代理、trailing 5日/次5日固定lag窗口、樣本內"
            "（非全市場）龍頭認定，訊號量級貼近雜訊而非方向判斷錯誤。"
        ),
        "refs": {
            "trials_ledger": ["#229"],
            "docs": ["HYPOTHESIS_QUEUE.md #65", "STRATEGY_GRAVEYARD.md f_leader_follower_lag", "TW_LEADS.md"],
        },
    },
    {
        "id": "66",
        "name": "美股年末稅損收割賣壓／一月效應（Tax-Loss Selling / January Effect）",
        "status": "FAIL",
        "concluded_at": "2026-09-09",
        "note": (
            "非0a節四條方向之一（屬HYPOTHESIS_QUEUE.md第⑮類「稅務動機機械性"
            "交易」機制，此機制台股不適用——台灣個人證券交易資本利得無需"
            "課稅，只能測美股），比照#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "199/200檔clean universe，排序變數改用YTD(1~10月)報酬避免套套"
            "邏輯，比較losers組(bottom decile)與對照組在12月(賣壓期)與次年"
            "1月(反轉期)報酬差，vs洗牌null。4項判準(TRAIN/VAL x 12月/1月)"
            "僅TRAIN次年1月單項過關(percentile=100.0)：12月賣壓期TRAIN="
            "40.6方向對未過門檻，VAL=10.2方向相反；次年1月反轉期VAL="
            "87.4方向對但些微未過90.0門檻。依事前綁定4項皆須過關判FAIL，"
            "不因VAL僅些微差距放寬。不泛化為一月效應完全不存在——反轉窗口"
            "方向兩期一致且TRAIN顯著，死的主要是12月賣壓這一半機制。"
        ),
        "refs": {
            "trials_ledger": ["#230"],
            "docs": ["HYPOTHESIS_QUEUE.md #66", "STRATEGY_GRAVEYARD.md us_tax_loss_selling_gate66"],
        },
    },
    {
        "id": "67",
        "name": "盤中零股交易比重（Odd-Lot Imbalance）portfolio層構造",
        "status": "FAIL",
        "concluded_at": "2026-09-10",
        "note": (
            "非0a節四條方向之一（屬HYPOTHESIS_QUEUE.md後續新增類別，零股委託簿"
            "失衡度訊號），比照#62先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "第1關cheap gate時序相關性CHEAP_PASS（邊緣過關，train僅3個快照、"
            "val percentile=90.7、val_mean_ic=0.0249），但第2關隨機控制組"
            "（N=100，TRAIN+VAL皆完整100 draws）決定性未過：升冪排序月頻挑"
            "失衡度最低TOP20做多，TRAIN真實報酬+4.93% vs 買進持有+9.52%、"
            "percentile=33.0；VAL真實報酬+10.80% vs 買進持有+61.94%、"
            "percentile=13.0（門檻90.0），兩期alpha皆不顯著、beta皆為正曝險。"
            "不泛化為訊號完全無效——死的是「升冪排序、月頻、純多方向、TOP20"
            "固定持股數」這個具體portfolio構造，訊號方向本身未被推翻。"
        ),
        "refs": {
            "trials_ledger": ["#231", "#232"],
            "docs": ["HYPOTHESIS_QUEUE.md #67", "STRATEGY_GRAVEYARD.md odd_lot_imbalance_portfolio_v1_gate67"],
        },
    },
    {
        "id": "68",
        "name": "券資比（Short-to-Margin Ratio）",
        "status": "FAIL",
        "concluded_at": "2026-09-10",
        "note": (
            "非0a節四條方向之一（屬HYPOTHESIS_QUEUE.md「資金結構失衡驅動」類別，"
            "融券今日餘額/融資今日餘額比值），比照#62先例一併寫入本檔公開，"
            "避免遺失。"
        ),
        "summary": (
            "300檔樣本（248/300可用）第1關cheap IC gate：train mean_ic=-0.0056"
            "（n=74期）、val mean_ic=-0.0548（n=47期，hit_rate=0.64），null"
            "percentile=100.0（門檻90.0以上），train/val同號，機械判準本應"
            "PASS，但train/val的IC皆為負，與事前綁定「券資比越高、預期報酬"
            "越好」的正向假設方向相反，依腳本事前寫明規則override為FAIL，"
            "不因符合「同號」判準就宣稱通過。不泛化為只否證「原始比例、"
            "正向」這個具體構造，反向使用或其他變換未經測試。"
        ),
        "refs": {
            "trials_ledger": ["#233"],
            "docs": ["HYPOTHESIS_QUEUE.md #68", "STRATEGY_GRAVEYARD.md #68"],
        },
    },
    {
        "id": "69",
        "name": "台指選擇權未平倉量Put/Call比逆向情緒訊號",
        "status": "FAIL",
        "concluded_at": "2026-09-10",
        "note": (
            "非0a節四條方向之一（屬HYPOTHESIS_QUEUE.md衍生品情緒訊號類別，"
            "未平倉量口徑，與已FAIL的#31成交量口徑同源不同聚合），比照#62"
            "先例一併寫入本檔公開，避免遺失。"
        ),
        "summary": (
            "TXO日盤未平倉量Put/Call比預測次一交易日台股報酬。TRAIN"
            "(<=2020-12-31) n=1467，Pearson r=+0.0508（p=0.0519），null"
            "percentile=93.6；VAL(2020-12-31~2024-12-31) n=970，"
            "r=+0.0395（p=0.2188），null percentile=79.0（門檻90.0）。"
            "幅度非零、train/val同號、事前綁定方向皆正三項判準通過，但VAL"
            "贏過洗牌null未過（79.0<90.0），第4項未過即判FAIL。不泛化為"
            "訊號完全無效——TRAIN期percentile=93.6接近門檻、p=0.0519邊緣"
            "顯著，只是VAL期訊號明顯減弱，屬訓練期邊緣訊號、驗證期未能"
            "穩定重現。"
        ),
        "refs": {
            "trials_ledger": ["#239"],
            "docs": ["HYPOTHESIS_QUEUE.md #69", "STRATEGY_GRAVEYARD.md option_oi_pcr_gate69"],
        },
    },
]


# 2026-09-08 總司令裁示【外部策略三】第2點：每條外部（名家）策略須標來源與
# 「公開後衰減」風險。精簡版放這裡供 App 顯示用；完整文獻細節、citation、
# 同家族揭露見 `docs/EXTERNAL_STRATEGY_SOURCES.md`——那份是來源真相，這裡是
# 展示摘要，兩邊都要更新，不得只改一邊。
EXTERNAL_STRATEGIES = [
    {"name": "PEAD／SUE（盈餘意外延續）", "track": "TW", "code": "f_eps_surprise／f_revenue_surprise",
     "source": "Foster, Olsen & Shevlin (1984)；Bernard & Thomas (1989)",
     "status": "MIXED（f_eps_surprise 通過分母校正，f_revenue_surprise 降級FAIL）"},
    {"name": "Piotroski F-score", "track": "TW", "code": "piotroski_fscore",
     "source": "Piotroski (2000), Journal of Accounting Research", "status": "FAIL"},
    {"name": "Sloan 應計項目異常", "track": "TW", "code": "f_accruals",
     "source": "Sloan (1996), The Accounting Review", "status": "已測"},
    {"name": "Novy-Marx 毛利率溢酬", "track": "TW", "code": "f_gross_profitability",
     "source": "Novy-Marx (2013), Journal of Financial Economics", "status": "降級FAIL"},
    {"name": "殘差動量 Residual Momentum", "track": "TW", "code": "f_residual_momentum",
     "source": "Blitz, Huij & Martens (2011), Journal of Empirical Finance", "status": "FAIL"},
    {"name": "52週高點接近度", "track": "TW", "code": "f_52w_high_prox",
     "source": "George & Hwang (2004), The Journal of Finance", "status": "FAIL"},
    {"name": "Weinstein 第二階段 Stage Analysis", "track": "TW", "code": "weinstein_stage2",
     "source": "Weinstein (1988), Secrets for Profiting in Bull and Bear Markets", "status": "FAIL"},
    {"name": "BAB Betting Against Beta", "track": "TW", "code": "factor_ic_bab",
     "source": "Frazzini & Pedersen (2014), Journal of Financial Economics", "status": "已測"},
    {"name": "低波動異常", "track": "US", "code": "f_us_low_vol",
     "source": "Ang, Hodrick, Xing & Zhang (2006), The Journal of Finance", "status": "通過"},
    {"name": "12個月動量", "track": "US", "code": "f_us_momentum_12m",
     "source": "Jegadeesh & Titman (1993), The Journal of Finance", "status": "已測"},
    {"name": "短期反轉", "track": "US", "code": "f_us_reversal_1m",
     "source": "Jegadeesh (1990), The Journal of Finance", "status": "FAIL"},
    {"name": "帳面市值比（價值）", "track": "US", "code": "f_us_value_bm",
     "source": "Fama & French (1992), The Journal of Finance", "status": "已測"},
    {"name": "海龜法則 System 1（20/10突破）", "track": "FUT", "code": "fut_turtle_system1_20_10",
     "source": "Dennis, R.；整理見 Faith (2007), Way of the Turtle", "status": "FAIL（百分位57.5）",
     "family": "家族A（與Donchian/Keltner/CTA多時間框架同家族，5筆算2個獨立發現）"},
    {"name": "Donchian 通道完整版（55/20）", "track": "FUT", "code": "fut_donchian_full_55_20",
     "source": "Donchian, R. D.（1960年代）", "status": "FAIL（百分位54.0）", "family": "家族A"},
    {"name": "Keltner 通道突破（EMA20±2ATR10）", "track": "FUT", "code": "fut_keltner_breakout_20_2atr",
     "source": "Keltner (1960), How to Make Money in Commodities", "status": "FAIL（百分位78.8）", "family": "家族A"},
    {"name": "波動度突破（0.5×ATR20）", "track": "FUT", "code": "fut_vol_breakout_0p5atr",
     "source": "業界通用規則，無單一起源論文", "status": "FAIL（百分位7.0）", "family": "獨立"},
    {"name": "CTA多時間框架趨勢＋波動度目標", "track": "FUT", "code": "fut_cta_multi_tf_voltarget",
     "source": "業界系統化CTA常見構造，無單一起源論文", "status": "FAIL（百分位73.0）", "family": "家族A"},
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
        "external_strategies_note": (
            "2026-09-08總司令裁示【外部策略三】第2點：每條外部（名家）已發表策略"
            "皆標來源與『公開後衰減』風險——McLean & Pontiff (2016, Journal of "
            "Finance) 實證發現異常報酬因子發表後樣本外報酬平均衰減約1/3~1/2，"
            "不分市場、不分因子類型皆適用，這是所有下列項目共同的基準風險。"
            "完整文獻細節見 docs/EXTERNAL_STRATEGY_SOURCES.md。"
            "已知限制：App（index.html）目前尚未讀取本檔案顯示，UI串接待開發帽"
            "另開項目，本欄位目前只做到資料層標註。"
        ),
        "external_strategies": EXTERNAL_STRATEGIES,
    }
    out_path = "../data/signal_status.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print(f"寫入 {out_path}，共 {len(DIRECTIONS)} 條方向、{len(EXTERNAL_STRATEGIES)} 條外部策略")


if __name__ == "__main__":
    build()
