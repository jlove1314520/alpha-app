#!/usr/bin/env bash
# 先.一三五-1kd-a 甲（2026-11-05 [預設放行]，收件匣 039 定案甲）：market.yml rebase 衝突時逐檔取捨後繼續，不丟整班。
#
# 用法：在 `git rebase origin/main` 失敗後呼叫：bash .github/scripts/rebase_resolve_conflicts.sh <標籤>
#   - 共用追蹤檔（下面 SHARED 清單）→ 取 main 上的版本（rebase 中是 --ours），放棄本班對它的改動；
#   - 其他檔 → 取雲端本班版本（rebase 中是 --theirs）；
#   - git add 後 rebase --continue，印 ::warning:: 列出每個檔取了哪一邊。
# 回傳 0＝解決完成（rebase 已結束）；非 0＝解不了（已 rebase --abort），呼叫端照舊 exit 1。
# 自測：scripts/selftest_rebase_resolve_conflicts.sh（暫存 repo 合成三種衝突）。
set -u
LABEL="${1:-workflow}"
SHARED_RE='^(PENDING_QUEUE\.md|data/STATUS\.json|research/PROGRESS_HEARTBEAT\.jsonl|data/trials_index\.json)$'

in_rebase() { [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ]; }

fail() {
  echo "::warning::${LABEL} rebase衝突無法自動取捨：$1"
  git rebase --abort 2>/dev/null || true
  exit 1
}

in_rebase || fail "rebase 不在進行中（不是內容衝突）"

picks=""
for round in 1 2 3 4 5 6 7 8 9 10; do
  files=$(git diff --name-only --diff-filter=U)
  if [ -z "$files" ]; then
    fail "rebase 進行中但沒有衝突檔（第 ${round} 輪）"
  fi
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if printf '%s\n' "$f" | grep -Eq "$SHARED_RE"; then side="--ours"; name="main"; else side="--theirs"; name="本班"; fi
    if git checkout "$side" -- "$f" 2>/dev/null; then
      git add -- "$f" || fail "git add 失敗：$f"
    else
      # 一邊已刪除（modify/delete）：取的那一邊沒有這個檔 → 照取捨刪掉
      if git cat-file -e ":$([ "$side" = "--ours" ] && echo 2 || echo 3):$f" 2>/dev/null; then
        fail "checkout ${side} 失敗：$f"
      fi
      git rm -q --cached -- "$f" 2>/dev/null; rm -f -- "$f"
      name="${name}(刪除)"
    fi
    picks="${picks} ${f}→${name}"
  done <<< "$files"
  if ! GIT_EDITOR=true git rebase --continue >/dev/null 2>&1; then
    # 取捨後這個 commit 沒有任何變動（衝突檔全取 main 且沒有別的檔）→ 跳過這個空 commit
    if [ -z "$(git diff --name-only --diff-filter=U)" ] && git diff --cached --quiet; then
      GIT_EDITOR=true git rebase --skip >/dev/null 2>&1 || true
      picks="${picks}（空commit已跳過）"
    fi
  fi
  if ! in_rebase; then
    echo "::warning::${LABEL} rebase衝突已逐檔取捨（共用追蹤檔取 main、其他取本班，先.一三五-1kd-a）：${picks}"
    exit 0
  fi
  # 還在 rebase：可能是下一個 commit 又衝突，或 continue 本身失敗（沒有新的衝突檔 → 下一輪 fail）
done
fail "超過 10 輪仍未完成"
