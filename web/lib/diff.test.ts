import { describe, expect, it } from "vitest";
import { parseUnifiedDiff, type DiffLine } from "./diff";

// A realistic difflib output for the workbench's flagship case:
// set_entry_point -> add_edge(START, ...). Built exactly the way the backend
// builds it (unified_diff over splitlines(keepends=True), joined with "").
const DIFF = [
  "--- legacy.py",
  "+++ migrated.py",
  "@@ -1,6 +1,6 @@",
  " from typing_extensions import TypedDict",
  "-from langgraph.graph import StateGraph",
  "+from langgraph.graph import StateGraph, START",
  " ",
  " builder = StateGraph(State)",
  '-builder.set_entry_point("double")',
  '+builder.add_edge(START, "double")',
  "",
].join("\n");

function kinds(lines: DiffLine[]): string[] {
  return lines.map((l) => l.kind);
}

describe("parseUnifiedDiff", () => {
  it("returns [] for an empty diff (the clean/flag paths)", () => {
    expect(parseUnifiedDiff("")).toEqual([]);
  });

  it("classifies file headers, hunks, adds, dels and context", () => {
    expect(kinds(parseUnifiedDiff(DIFF))).toEqual([
      "file", "file", "hunk",
      "ctx", "del", "add", "ctx", "ctx", "del", "add",
    ]);
  });

  it("numbers lines from the hunk header, per side", () => {
    const lines = parseUnifiedDiff(DIFF);
    const del = lines.filter((l) => l.kind === "del");
    const add = lines.filter((l) => l.kind === "add");
    const ctx = lines.filter((l) => l.kind === "ctx");
    // dels advance only the old side, adds only the new, ctx both.
    expect(del.map((l) => l.kind === "del" && l.oldNo)).toEqual([2, 5]);
    expect(add.map((l) => l.kind === "add" && l.newNo)).toEqual([2, 5]);
    expect(
      ctx.map((l) => l.kind === "ctx" && [l.oldNo, l.newNo]),
    ).toEqual([[1, 1], [3, 3], [4, 4]]);
  });

  it("does not confuse +++/--- file headers with add/del lines", () => {
    const [a, b] = parseUnifiedDiff(DIFF);
    expect(a).toEqual({ kind: "file", text: "--- legacy.py" });
    expect(b).toEqual({ kind: "file", text: "+++ migrated.py" });
  });

  it("strips the one-char prefix but keeps indentation intact", () => {
    const lines = parseUnifiedDiff(
      "@@ -1,1 +1,1 @@\n-    old()\n+    new()\n",
    );
    expect(lines[1]).toMatchObject({ kind: "del", text: "    old()" });
    expect(lines[2]).toMatchObject({ kind: "add", text: "    new()" });
  });

  it("handles a hunk header without explicit counts (@@ -1 +1 @@)", () => {
    const lines = parseUnifiedDiff("@@ -3 +7 @@\n-a\n+b\n");
    expect(lines[1]).toMatchObject({ kind: "del", oldNo: 3 });
    expect(lines[2]).toMatchObject({ kind: "add", newNo: 7 });
  });

  it("restarts numbering at every hunk", () => {
    const lines = parseUnifiedDiff(
      "@@ -1,1 +1,1 @@\n-a\n+b\n@@ -10,1 +12,1 @@\n-c\n+d\n",
    );
    expect(lines[4]).toMatchObject({ kind: "del", oldNo: 10 });
    expect(lines[5]).toMatchObject({ kind: "add", newNo: 12 });
  });

  it("treats a bare empty line as empty context, not as add/del", () => {
    const lines = parseUnifiedDiff("@@ -1,2 +1,2 @@\n a\n\n");
    expect(lines[2]).toMatchObject({ kind: "ctx", text: "", oldNo: 2, newNo: 2 });
  });
});
