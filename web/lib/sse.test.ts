import { describe, expect, it } from "vitest";
import { createSseParser } from "./sse";

/** Feed `chunks` into a fresh parser and collect emitted payloads. */
function run(chunks: string[]): string[] {
  const out: string[] = [];
  const parser = createSseParser((p) => out.push(p));
  for (const c of chunks) parser.push(c);
  return out;
}

describe("createSseParser", () => {
  it("parses a single complete frame", () => {
    expect(run(['data: {"type":"token","v":"hi"}\n\n'])).toEqual([
      '{"type":"token","v":"hi"}',
    ]);
  });

  it("parses multiple frames arriving in one chunk", () => {
    expect(run(["data: a\n\ndata: b\n\ndata: c\n\n"])).toEqual(["a", "b", "c"]);
  });

  it("re-assembles a frame split mid-payload across chunks", () => {
    expect(run(['data: {"type":"tok', 'en","v":"x"}\n\n'])).toEqual([
      '{"type":"token","v":"x"}',
    ]);
  });

  it("handles the \\n\\n separator itself split across chunks", () => {
    expect(run(["data: a\n", "\ndata: b\n\n"])).toEqual(["a", "b"]);
  });

  it("handles a chunk boundary between two frames", () => {
    expect(run(["data: a\n\n", "data: b\n\n"])).toEqual(["a", "b"]);
  });

  it("handles CRLF line endings, including a split \\r\\n\\r\\n", () => {
    expect(run(["data: a\r\n\r", "\ndata: b\r\n\r\n"])).toEqual(["a", "b"]);
  });

  it("emits one payload per push callback in stream order under heavy fragmentation", () => {
    // Byte-by-byte delivery is the worst case a proxy can produce.
    const stream = "data: one\n\ndata: two\n\ndata: three\n\n";
    expect(run(stream.split(""))).toEqual(["one", "two", "three"]);
  });

  it("ignores frames without a data line (comments, id/event-only)", () => {
    expect(run([": keep-alive\n\n", "event: ping\nid: 3\n\n", "data: x\n\n"])).toEqual([
      "x",
    ]);
  });

  it("joins multiple data lines in one frame with \\n (SSE spec)", () => {
    expect(run(["data: line1\ndata: line2\n\n"])).toEqual(["line1\nline2"]);
  });

  it("strips at most one leading space after the colon", () => {
    expect(run(["data:  padded\n\n", "data:tight\n\n"])).toEqual([" padded", "tight"]);
  });

  it("does not emit a trailing incomplete frame", () => {
    expect(run(["data: done\n\ndata: partial"])).toEqual(["done"]);
  });
});
