# 稽核.六續五：BLAS執行緒數對commit與速度的取捨（量測）

腳本`mem_blas_threads_bench.py`；負載＝`factor_ic.load_sample_with_factors`25檔＋`prepare_market_data(TAIEX)`（含import factor_ic），
每設定3次取中位數；子行程量`PeakPagefileUsage`（commit峰值）與`PeakWorkingSetSize`。只讀快取、不碰holdout、零API。

| OPENBLAS/OMP/MKL_NUM_THREADS | 次數 | 可用檔數 | wall-clock中位數(秒) | 相對預設 | commit峰值中位數(MB) | WorkingSet峰值中位數(MB) |
|---|---|---|---|---|---|---|
| 預設(不設，24核) | 3 | 23 | 57.2 | +0% | 2958 | 951 |
| 4 | 3 | 23 | 58.0 | +1% | 1245 | 914 |
| 1 | 3 | 23 | 60.6 | +6% | 918 | 924 |

## 結論與提案（分支(a)成立；**本項不改任何啟動器/排程，動排程須另案提案**）

- 推論驗證：commit峰值由2,958MB降到1,245MB（4執行緒，−1.7GB）／918MB（1執行緒，−2.0GB），WorkingSet峰值不變（約910~950MB）——
  與`INCIDENTS.md`稽核.六續四的推論一致：差額是BLAS執行緒緩衝區的commit預留，不是實體記憶體。
- 速度代價：4執行緒+1%（在3次抖動範圍內）、1執行緒+6%，均<20%門檻。此負載以pandas/parquet讀取為主，BLAS執行緒數對它幾乎無影響。
- **建議（提案，未執行）**：在`run-*.ps1`自走啟動器（marathon/hypothesis_queue/dev_queue）與批次腳本入口設`OPENBLAS_NUM_THREADS=4`
  （`OMP_NUM_THREADS`/`MKL_NUM_THREADS`同）——單行程可省約1.7GB commit，收益是多行程並行時延後commit上限（實測當時剩餘8.4GB/50GB）；
  選4而非1是因為速度代價與1差5個百分點、且保留矩陣運算類工作的並行度。**需總司令核准後才動排程腳本**（提案先於執行：屬架構/參數變更）。
- 誠實限制：只量了一條代表性負載（25檔因子載入＋TAIEX，含import factor_ic）；矩陣運算為主的腳本（bootstrap、大量
  `np.linalg`/協方差）在threads=4/1下可能明顯變慢，未量測。commit剩餘量是單一時點快照，非長期趨勢。
