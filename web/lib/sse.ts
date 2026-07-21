// Incremental SSE frame parser, extracted from the /agent/stream reader so the
// buffer-split logic is unit-testable and Stage 2's /migrate stream can reuse
// it. This is the exact code path that breaks silently: a frame (or even the
// "\n\n" separator itself) can arrive split across two network chunks, and a
// naive per-chunk split drops or corrupts events without any error.
//
// The parser is transport-level only: it re-assembles frames and emits each
// frame's `data:` payload as a string. Interpreting the payload (JSON, event
// dispatch) stays with the caller — different streams carry different shapes.

export type SseParser = {
  /** Feed the next decoded chunk from the network. May emit 0..n payloads. */
  push: (chunk: string) => void;
};

export function createSseParser(onData: (payload: string) => void): SseParser {
  let buffer = "";
  // Frames end with a blank line; tolerate both \n\n and \r\n\r\n. Searching
  // the *accumulated* buffer each push means a separator split across chunks
  // ("…\r\n\r" + "\n…") is found naturally once the second half arrives.
  const FRAME_SEP = /\r?\n\r?\n/;
  return {
    push(chunk: string) {
      buffer += chunk;
      for (;;) {
        const sep = FRAME_SEP.exec(buffer);
        if (!sep) return; // incomplete frame — keep buffering
        const frame = buffer.slice(0, sep.index);
        buffer = buffer.slice(sep.index + sep[0].length);
        // Per the SSE spec: concatenate all data lines of the frame with \n,
        // stripping at most one leading space after the colon. Frames without
        // a data line (comments, event/id-only) are ignored.
        const payload = frame
          .split(/\r?\n/)
          .filter((l) => l.startsWith("data:"))
          .map((l) => l.slice(5).replace(/^ /, ""))
          .join("\n");
        if (payload) onData(payload);
      }
    },
  };
}
