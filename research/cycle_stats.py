# -*- coding: utf-8 -*-
"""解析一輪馬拉松 `claude -p --output-format stream-json --verbose` 的 jsonl 輸出，算出這輪的
「死因」、花費、讀取量（2026-09-05，提案選項1修法C／F 的量測工具）。

用法：python research/cycle_stats.py <cycle.jsonl> [--write-last]
輸出 JSON：
  reason        OK / BUDGET / TIMEOUT(由ps1填) / ERROR / UNKNOWN
  cost_usd      total_cost_usd
  num_turns, duration_min
  read_bytes    所有 tool_result 內容的位元組數合計（= 這輪實際餵回模型的檔案/指令輸出量）
  read_bytes_by_tool  {Read: x, Bash: y, Grep: z, ...}
  biggest_reads 前5大單筆 tool_result（工具、檔案/指令、位元組）
  usage         input/cache_creation/cache_read/output tokens
--write-last 會把結果併入 research/data/marathon_cycle_last.json（ps1 呼叫時用）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RESEARCH = Path(__file__).resolve().parent
LAST_PATH = RESEARCH / "data" / "marathon_cycle_last.json"


def analyze(path: Path) -> dict:
    out = {"reason": "UNKNOWN", "cost_usd": None, "num_turns": None, "duration_min": None,
           "read_bytes": 0, "read_bytes_by_tool": {}, "biggest_reads": [], "usage": None, "subtype": None,
           "events": 0, "tool_uses": 0}
    pending: dict[str, tuple[str, str]] = {}  # tool_use_id -> (tool name, short input)
    reads: list[tuple[int, str, str]] = []
    if not path.exists():
        out["reason"] = "NO_OUTPUT"
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        out["events"] += 1
        t = d.get("type")
        if t == "assistant":
            for c in d.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    out["tool_uses"] += 1
                    inp = c.get("input") or {}
                    short = inp.get("file_path") or inp.get("command") or inp.get("pattern") or ""
                    pending[c.get("id")] = (c.get("name", "?"), str(short)[:120])
        elif t == "user":
            for c in d.get("message", {}).get("content", []):
                if c.get("type") == "tool_result":
                    cont = c.get("content")
                    s = cont if isinstance(cont, str) else json.dumps(cont, ensure_ascii=False)
                    n = len(s.encode("utf-8"))
                    name, short = pending.get(c.get("tool_use_id"), ("?", ""))
                    out["read_bytes"] += n
                    out["read_bytes_by_tool"][name] = out["read_bytes_by_tool"].get(name, 0) + n
                    reads.append((n, name, short))
        elif t == "result":
            out["subtype"] = d.get("subtype")
            out["cost_usd"] = d.get("total_cost_usd")
            out["num_turns"] = d.get("num_turns")
            out["duration_min"] = round((d.get("duration_ms") or 0) / 60000, 2)
            out["usage"] = {k: (d.get("usage") or {}).get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")}
            st = d.get("subtype") or ""
            if st == "success" and not d.get("is_error"):
                out["reason"] = "OK"
            elif "budget" in st or d.get("terminal_reason") == "budget_exhausted":
                out["reason"] = "BUDGET"
            elif "max_turns" in st:
                out["reason"] = "MAX_TURNS"
            else:
                out["reason"] = "ERROR"
    reads.sort(reverse=True)
    out["biggest_reads"] = [{"bytes": n, "tool": name, "what": short} for n, name, short in reads[:5]]
    out["read_kb"] = round(out["read_bytes"] / 1024, 1)
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    res = analyze(Path(sys.argv[1]))
    if "--write-last" in sys.argv:
        LAST_PATH.parent.mkdir(parents=True, exist_ok=True)
        base = {}
        if LAST_PATH.exists():
            try:
                base = json.loads(LAST_PATH.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError:
                base = {}
        # ps1 先寫 started/ended/reason(TIMEOUT時) 進來；這裡只在 ps1 沒判定 TIMEOUT 時覆寫 reason
        if base.get("reason") != "TIMEOUT":
            base["reason"] = res["reason"]
        base.update({k: v for k, v in res.items() if k != "reason"})
        LAST_PATH.write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
