// Parser for the server-side unified diff (`result.diff` from /migrate —
// produced by Python's stdlib difflib). Pure and unit-tested: the component
// in components/diff-view.tsx only maps the parsed lines to table rows.
//
// Why parse at all instead of dumping <pre>: the UI needs per-line colour,
// old/new line numbers (tabular, like every code-review tool), and gutters
// that don't pollute copy/paste — all of which need structure, not a string.

export type DiffLine =
  /** `--- legacy.py` / `+++ migrated.py` file headers. */
  | { kind: "file"; text: string }
  /** `@@ -a,b +c,d @@` hunk header. */
  | { kind: "hunk"; text: string }
  | { kind: "add"; text: string; newNo: number }
  | { kind: "del"; text: string; oldNo: number }
  | { kind: "ctx"; text: string; oldNo: number; newNo: number };

const HUNK_RE = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/;

export function parseUnifiedDiff(diff: string): DiffLine[] {
  if (!diff) return [];
  const out: DiffLine[] = [];
  let oldNo = 0;
  let newNo = 0;
  // difflib joins lines that already carry their own "\n"; a trailing "" after
  // the final newline is split debris, not an empty context line — drop it.
  const lines = diff.split("\n");
  if (lines.length > 0 && lines[lines.length - 1] === "") lines.pop();

  for (const line of lines) {
    const hunk = HUNK_RE.exec(line);
    if (hunk) {
      oldNo = parseInt(hunk[1], 10);
      newNo = parseInt(hunk[2], 10);
      out.push({ kind: "hunk", text: line });
    } else if (line.startsWith("+++") || line.startsWith("---")) {
      // Must be tested BEFORE the one-char +/- prefixes they start with.
      out.push({ kind: "file", text: line });
    } else if (line.startsWith("+")) {
      out.push({ kind: "add", text: line.slice(1), newNo: newNo++ });
    } else if (line.startsWith("-")) {
      out.push({ kind: "del", text: line.slice(1), oldNo: oldNo++ });
    } else {
      // Context lines are prefixed with a single space; tolerate a bare ""
      // (an empty source line whose leading space got trimmed in transit).
      out.push({
        kind: "ctx",
        text: line.startsWith(" ") ? line.slice(1) : line,
        oldNo: oldNo++,
        newNo: newNo++,
      });
    }
  }
  return out;
}
