#!/usr/bin/env bash
# 先.一三五-1kd-a 自測：暫存 repo 合成 market.yml rebase 衝突，驗 .github/scripts/rebase_resolve_conflicts.sh。
# 情境：①共用追蹤檔衝突→取 main ②資料檔衝突→取本班 ③兩者同時＋不衝突檔保留 ④rebase 未進行→回非 0
#      ⑤只有共用檔衝突且 commit 沒別的變動→空 commit 跳過、仍回 0
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="$HERE/.github/scripts/rebase_resolve_conflicts.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; failn=0
ok() { if [ "$1" = "$2" ]; then pass=$((pass+1)); echo "PASS $3"; else failn=$((failn+1)); echo "FAIL $3（得 $1，應 $2）"; fi; }

setup() {
  cd "$T"; rm -rf "$T/origin" "$T/w" "$T/o"
  git init -q --bare -b main "$T/origin"
  git -c core.autocrlf=false clone -q -c core.autocrlf=false "$T/origin" "$T/o" 2>/dev/null
  cd "$T/o"; git config user.email t@t; git config user.name t; git config core.autocrlf false
  mkdir -p data research
  echo base > PENDING_QUEUE.md; echo base > data/quotes.json; echo base > data/other.json; echo base > research/PROGRESS_HEARTBEAT.jsonl
  git add -A; git commit -qm base; git branch -M main; git push -q origin main
  git -c core.autocrlf=false clone -q -c core.autocrlf=false "$T/origin" "$T/w" 2>/dev/null
  cd "$T/w"; git config user.email t@t; git config user.name t; git config core.autocrlf false
}
main_push() { (cd "$T/o"; for f in "$@"; do echo main > "$f"; done; git add -A; git commit -qm m; git push -q origin main); }
cloud_commit() { cd "$T/w"; for f in "$@"; do echo cloud > "$f"; done; git add -A; git commit -qm c; git fetch -q origin; }

# ①
setup; main_push PENDING_QUEUE.md; cloud_commit PENDING_QUEUE.md data/other.json
git rebase origin/main >/dev/null 2>&1; bash "$TOOL" t >/dev/null; rc=$?
ok "$rc" 0 "①回 0"; ok "$(cat PENDING_QUEUE.md)" main "①共用檔取 main"; ok "$(cat data/other.json)" cloud "①不衝突檔保留本班"
# ②
setup; main_push data/quotes.json; cloud_commit data/quotes.json
git rebase origin/main >/dev/null 2>&1; bash "$TOOL" t >/dev/null; rc=$?
ok "$rc" 0 "②回 0"; ok "$(cat data/quotes.json)" cloud "②資料檔取本班"; ok "$(git log --oneline origin/main..HEAD | wc -l | tr -d ' ')" 1 "②本班 commit 在 main 之上"
# ③
setup; main_push PENDING_QUEUE.md data/quotes.json research/PROGRESS_HEARTBEAT.jsonl; cloud_commit PENDING_QUEUE.md data/quotes.json research/PROGRESS_HEARTBEAT.jsonl data/other.json
git rebase origin/main >/dev/null 2>&1; out=$(bash "$TOOL" t); rc=$?
ok "$rc" 0 "③回 0"; ok "$(cat PENDING_QUEUE.md)$(cat research/PROGRESS_HEARTBEAT.jsonl)" mainmain "③兩個共用檔取 main"
ok "$(cat data/quotes.json)$(cat data/other.json)" cloudcloud "③資料檔取本班"
ok "$(echo "$out" | grep -c '::warning::')" 1 "③印一條 warning"
git push -q origin HEAD:main 2>/dev/null; ok "$?" 0 "③可 push（fast-forward）"
# ④
setup; bash "$TOOL" t >/dev/null; ok "$?" 1 "④rebase 未進行→回 1"
# ⑤
setup; main_push PENDING_QUEUE.md; cloud_commit PENDING_QUEUE.md
git rebase origin/main >/dev/null 2>&1; bash "$TOOL" t >/dev/null; rc=$?
ok "$rc" 0 "⑤空 commit 跳過回 0"; ok "$(git rev-parse HEAD)" "$(git rev-parse origin/main)" "⑤HEAD＝main"
[ -d "$(git rev-parse --git-path rebase-merge)" ] && r=yes || r=no; ok "$r" no "⑤rebase 已結束"

echo "合計 PASS $pass／FAIL $failn"
[ "$failn" -eq 0 ] && echo "ALL PASS"
exit "$failn"
