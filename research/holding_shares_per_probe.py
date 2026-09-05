"""Probe: 假設#38（股東持股分級表大戶集中度變化）的地基查證——FinMind
`TaiwanStockHoldingSharesPer`（股東持股分級表）這個dataset實際長什麼樣子、
欄位名稱、頻率、大戶/散戶級距怎麼切，決定這條假設的因子計算方式是否可行。

背景：`HYPOTHESIS_QUEUE_PROTOCOL.md`第1節指引——佇列#1~37已全數結案（見
`HYPOTHESIS_QUEUE.md`「排隊順序總結」），#5/#6/#8/#10仍卡外部依賴未解鎖
（`BACKLOG.md`重新查證確認`value_board_v2`仍是`回測未通過`、題材動能榜
PIT引擎仍未建置），佇列實質已空，本輪設計新假設軸#38。

經濟機制（跟已測過的37條逐一核對，確認真正不同，非換皮）：
- 跟三大法人買賣超（日頻資金流）、融資餘額（散戶槓桿水位）、融券使用率
  （知情放空者）都不同——這個dataset量的是「持股結構」本身（誰持有多少
  股），是週頻的慢變數，不是任何一天的成交/委買賣行為。
- 經濟故事：大戶（例如>=400張級距）持股占比上升+散戶（<=1張級距）占比
  下降＝籌碼往少數人手上集中，可能代表知情大戶正在吸籌（informed
  accumulation）；反向則可能是出貨給散戶（distribution），跟`f_bab`/
  `f_low_vol`這類橫斷面排序機制在計算上完全不同源頭。

只做1c等級的infra probe：短窗口、少量請求，先確認dataset存在、欄位、
更新頻率，不做全歷史回補（那是下一輪的事，視這輪探查結果而定）。

All fetches go through finmind_client.load_dev()（holdout-safe），依
CONSTITUTION.md規則。
"""
from __future__ import annotations

from finmind_client import load_dev

PROBE_DATA_ID = "2330"  # 台積電，樣本股，資料應該最完整
PROBE_START = "2024-01-01"
PROBE_END = "2024-03-31"


def probe_one(dataset: str, data_id: str) -> None:
    print(f"\n=== dataset={dataset!r} data_id={data_id!r} ===")
    try:
        df = load_dev(dataset, data_id, start_date=PROBE_START, end_date=PROBE_END)
    except Exception as e:  # noqa: BLE001 -- 探查階段要看到每一種失敗模式，不要讓探查腳本自己壞掉
        print(f"FAILED: {type(e).__name__}: {e}")
        return

    if df.empty:
        print("回傳空的dataframe（dataset/data_id組合可能不對，或這個窗口沒資料）")
        return

    print(f"rows: {len(df)}")
    print(f"columns: {list(df.columns)}")
    print(df.head(20).to_string())
    if "HoldingSharesLevel" in df.columns:
        print("\n持股級距種類:")
        print(df["HoldingSharesLevel"].unique())
    if "date" in df.columns:
        print(f"\n日期唯一值（前10個，看更新頻率）: {sorted(df['date'].unique())[:10]}")


def main() -> None:
    probe_one("TaiwanStockHoldingSharesPer", PROBE_DATA_ID)


if __name__ == "__main__":
    main()
