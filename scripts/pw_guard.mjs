// 2026-10-11 先.七十-3：Playwright 瀏覽器「一定關得掉」的共用守門。
// 根因：測試腳本中途拋錯、被砍（DevQueue 逾時 taskkill）、或 browser.close() 卡住時，headless chrome 會留下來吃記憶體。
// 做法：
//   1. launchGuarded() 啟動時在 chrome 命令列加兩個無作用的標記參數：
//        --alpha-pw-owner=<擁有者>（環境變數 ALPHA_PW_OWNER，DevQueue 每輪設成 devqueue-<cycle_id>；沒設＝manual）
//        --alpha-pw-node=<本 node 行程 PID>
//      並在 research/.pw_pids/ 寫一個 PID 檔（擁有者、node PID、腳本、啟動時間），正常結束時刪除。
//      run-dev-queue-cycle.ps1 每輪收尾只依「自己的擁有者標記」清理殘留的 chrome／node（只清自己啟動的）。
//   2. close()：browser.close() 超過 30 秒沒完成 → 用標記參數找出本次啟動的 chrome 程序強制結束。
//   3. 整體硬上限（預設 20 分鐘）、SIGINT／SIGTERM、未接住的例外 → 一律先 close() 再結束行程。
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PID_DIR = path.join(ROOT, "research", ".pw_pids");
export const OWNER = (process.env.ALPHA_PW_OWNER || "manual").replace(/[^A-Za-z0-9_.-]/g, "_");
const CLOSE_TIMEOUT_MS = 30 * 1000;

function forceKillOwnChrome(label) {
  if (process.platform !== "win32") return;
  // Playwright 的 headless 瀏覽器程序名是 chrome-headless-shell.exe（有頭模式才是 chrome.exe）；只有主程序帶標記，
  // 用 taskkill /T 連同它的子程序（renderer／gpu）一起結束。
  const ps = `Get-CimInstance Win32_Process -Filter "Name='chrome.exe' or Name='chrome-headless-shell.exe' or Name='headless_shell.exe'" | ` +
    `Where-Object { $_.CommandLine -like '*--alpha-pw-node=${process.pid} *' -or $_.CommandLine -like '*--alpha-pw-node=${process.pid}' } | ` +
    `ForEach-Object { taskkill /T /F /PID $_.ProcessId | Out-Null; $_.ProcessId }`;
  try {
    const out = execFileSync("powershell", ["-NoProfile", "-Command", ps], { encoding: "utf8", timeout: 20000 }).trim();
    console.error(`[${label}] 已強制結束本次啟動的瀏覽器程序：${out ? out.split(/\s+/).length : 0} 支`);
  } catch (e) {
    console.error(`[${label}] 強制結束瀏覽器失敗：${e.message || e}`);
  }
}

export async function launchGuarded(browserType, launchOpts = {}, { label = "playwright", hardTimeoutMs = 20 * 60 * 1000 } = {}) {
  const args = [...(launchOpts.args || []), `--alpha-pw-owner=${OWNER}`, `--alpha-pw-node=${process.pid}`];
  const browser = await browserType.launch({ ...launchOpts, args });
  let pidFile = null;
  try {
    fs.mkdirSync(PID_DIR, { recursive: true });
    pidFile = path.join(PID_DIR, `${OWNER}__${process.pid}.json`);
    fs.writeFileSync(pidFile, JSON.stringify({ owner: OWNER, node_pid: process.pid, script: label, started: new Date().toISOString() }));
  } catch (e) { console.warn(`[${label}] 寫 PID 檔失敗（不影響測試）：${e.message || e}`); pidFile = null; }

  let closing = null;
  const close = () => {
    if (closing) return closing;
    closing = (async () => {
      let timer;
      const timedOut = new Promise((resolve) => { timer = setTimeout(() => resolve("timeout"), CLOSE_TIMEOUT_MS); });
      try {
        const r = await Promise.race([browser.close().then(() => "ok", () => "error"), timedOut]);
        if (r !== "ok") {
          console.error(`[${label}] browser.close() ${r === "timeout" ? "超過 30 秒" : "失敗"}，改為強制結束`);
          forceKillOwnChrome(label);
        }
      } finally {
        clearTimeout(timer);
        if (pidFile) { try { fs.unlinkSync(pidFile); } catch { /* 已不存在 */ } }
      }
    })();
    return closing;
  };

  const hard = setTimeout(async () => {
    console.error(`[${label}] 整體執行超過 ${Math.round(hardTimeoutMs / 60000)} 分鐘，強制關閉瀏覽器並以 exit 1 結束`);
    await close();
    process.exit(1);
  }, hardTimeoutMs);
  hard.unref();
  const onSignal = (sig) => async () => { console.error(`[${label}] 收到 ${sig}，關閉瀏覽器後結束`); await close(); process.exit(130); };
  for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) process.once(sig, onSignal(sig));
  process.once("uncaughtException", async (e) => { console.error(`[${label}] 未接住的例外：`, e); await close(); process.exit(1); });
  process.once("unhandledRejection", async (e) => { console.error(`[${label}] 未接住的 Promise 失敗：`, e); await close(); process.exit(1); });
  return { browser, close, clearHard: () => clearTimeout(hard) };
}
