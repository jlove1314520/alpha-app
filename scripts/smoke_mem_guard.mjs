// 冒煙測試開跑前的記憶體保護（先.一三八-B3，Cowork 收件匣 027 B3）。
// 背景：10/27 冒煙測試被系統以記憶體不足中止。開跑前讀可用實體記憶體，
// <1.5GB 印原因、等 10 分鐘再量一次；仍不足就回傳 false，由呼叫端以
// 「記憶體不足、未執行」非 0 結束——不得假裝通過。
// 測試用環境變數：ALPHA_SMOKE_FAKE_FREEMEM_MB（逗號分隔，依序當作第 1、2 次量到的 MB）、
// ALPHA_SMOKE_MEM_WAIT_MS（等待毫秒，預設 600000）。
import os from "node:os";

export const MIN_FREE_MB = 1536;

export async function memGuard({ read, sleep, waitMs, log = console.log } = {}) {
  const fake = (process.env.ALPHA_SMOKE_FAKE_FREEMEM_MB || "").split(",").filter(Boolean).map(Number);
  let n = 0;
  read = read || (() => (fake.length ? fake[Math.min(n++, fake.length - 1)] : os.freemem() / 1048576));
  sleep = sleep || ((ms) => new Promise((r) => setTimeout(r, ms)));
  waitMs = waitMs ?? Number(process.env.ALPHA_SMOKE_MEM_WAIT_MS || 600000);
  const first = read();
  if (first >= MIN_FREE_MB) return { ok: true, free_mb: Math.round(first), retried: false };
  log(`[記憶體保護] 可用實體記憶體 ${Math.round(first)}MB < ${MIN_FREE_MB}MB，等 ${Math.round(waitMs / 60000)} 分鐘再量一次（先.一三八-B3）`);
  await sleep(waitMs);
  const second = read();
  if (second >= MIN_FREE_MB) return { ok: true, free_mb: Math.round(second), retried: true };
  log(`[記憶體保護] 重量仍只有 ${Math.round(second)}MB < ${MIN_FREE_MB}MB：記憶體不足、未執行冒煙測試（不算通過）`);
  return { ok: false, free_mb: Math.round(second), retried: true };
}
