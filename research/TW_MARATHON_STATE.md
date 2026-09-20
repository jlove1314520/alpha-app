# TW_MARATHON_STATE.md — 台股軌斷點狀態（覆寫式）

**這份檔案只描述台股軌「現在」的狀態，會被覆寫，不是 append-only。** 細節動作記錄看 `TW_LOG.md`；候選判定看 `TW_LEADS.md`；累積試驗數看 `TRIALS_LEDGER.md`；操作規則看 `MARATHON_PROTOCOL.md`。

> 2026-09-05 起本檔只保留最新 3 則（每輪開工簡報會印這 3 則）；更早的已原文搬到 `TW_STATE_ARCHIVE.md`（append-only），需要時 grep 那裡。

**最後更新：2026-09-20T22:42:21+08:00（馬拉松第584輪）**——取鎖乾淨。戴研究帽做`原子.五B`計算層：`ATOM_FIN_CHANNEL_B_SPEC.md`事前登記（132表達式/264測試）→`fin_atom_ic_map_b.py`→Tier A(204檔)/B(567檔)全量跑完；K=5僅4族、檢定力低，機械結果FAIL但不可外推（SPEC第6節）；尚未登記、判定留驗證帽輪次（`PENDING_QUEUE.md`原子.五B進度）。下一步：驗證帽寫`FIN_ATOM_CHANNEL_B.md`＋register_trial；`籌碼原子.補出借總量快取`第2批續投（slb_backfill_b1結束後）。

**最後更新：2026-09-20T20:12+08:00（馬拉松第583輪）**——取鎖乾淨。戴研究帽寫`原子.六`籌碼原子家族規格`ATOM_CHIP_IC_MAP_SPEC.md`（事前登記，89表達式×2horizon＝178測試，Tier A 67本機即可／Tier B 22待借券賣出餘額回補；宇宙U＝392檔；T86起點2012-05-02僅上市、無2011窗；全籌碼原子lag1日）。未算任何IC、無試驗登記、N不變。同輪解除`財報原子.補快取`阻塞並投遞job`20260920-200720-e34b`（下一輪收成）；另補入`籌碼原子.補借券快取`／`籌碼原子.出借總量查證`。**下一步**：`原子.六`實作`chip_atom_library.py`→15檔smoke→Tier A全量。

**最後更新：2026-09-20T17:50+08:00（馬拉松第582輪）**——取鎖`LOCK_STALE`（上一輪TIMEOUT被砍，非卡死）。戴研究帽做`原子.五`計算層：新增`fin_atom_ic_map.py`（145表達式、斷言=SPEC）、`fin_atom_ic_map_aggregate.py`；15檔smoke→30檔記憶體驗證(private峰值1867MB=import基線內)→Tier A(204檔)/Tier B(407檔，須以列數>0判宇宙，size口徑會誤算549)全量跑完，holdout未動。聚合初步：Tier A 60日五窗全同號6/26(p=0.0046)、20日3/26(p=0.22)，但57式僅14~17獨立族→p高估，**未下判定**；族層級規則已預寫進`PENDING_QUEUE.md`原子.五進度。下一輪(驗證帽)：族層級重算→`FIN_ATOM_IC_MAP.md`→`register_trial()`登記290測試→依SPEC§7判定。另發現`補快取`第1批178檔全空表(ETF)。


