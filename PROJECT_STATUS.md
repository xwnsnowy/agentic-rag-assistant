# Project Status — Agentic RAG Assistant

> Tổng kết master toàn dự án. Chi tiết từng phase: [PHASE_0.md](PHASE_0.md) ·
> [PHASE_1.md](PHASE_1.md) · [PHASE_2.md](PHASE_2.md) · eval sâu: [ai/eval/README.md](ai/eval/README.md).

- **Live demo:** https://agentic-rag-assistant.vercel.app
- **Repo:** https://github.com/xwnsnowy/agentic-rag-assistant
- **Stack live:** Next.js @ Vercel → FastAPI @ Render → Postgres+pgvector @ Neon

| Phase | Trạng thái | Điểm nhấn |
|---|---|---|
| 0 — Foundation | ✅ | pgvector + corpus LangGraph v1.0 |
| 1 — RAG + Eval (flagship) | ✅ | hybrid+rerank > baseline, Ragas thật + LLM-judge |
| 2 — Agent layer | ✅ | LangGraph agent, tool-selection 0.917, guardrails |
| 2.5 — Agent trong web UI | ✅ | toggle RAG⇄Agent + badge tool |
| 3 — Deploy production | ✅ | live end-to-end, CORS thông |
| 3+ — Expansions | ✅ | shadcn UI + dark mode, Markdown, query-rewrite, semantic cache (13×), injection eval (1.000), **multi-turn memory** (checkpointer), **/eval dashboard**, CI/CD — xem [ROADMAP.md](ROADMAP.md) |

---

## 1. Đã làm được — chi tiết

### Phase 0 — Nền tảng & dữ liệu
- **DB:** Neon Postgres + pgvector; bảng `documents`, `chunks` (`embedding vector(1536)`,
  `metadata jsonb`, `tsv tsvector`, index HNSW cosine + GIN full-text).
- **Corpus:** docs LangGraph **v1.0 pin tag `1.0.10`**, lấy bản markdown `.md` (Mintlify) →
  **12 trang / ~325 KB**, provenance trong `ai/data/manifest.json`.
- **Scaffold:** FastAPI (`ai/`) + Next.js (`web/`), health-check nối nhau.
- **Files:** `ai/app/{config,db,embeddings,main}.py`, `ai/migrations/001_init.sql`,
  `ai/scripts/{init_db,seed_chunk,fetch_corpus}.py`.

### Phase 1 — RAG core + Eval (FLAGSHIP)
- **Chunking** heading-based (không cắt code block, gắn metadata) → **244 chunks**.
- **Retrieval 3 chiến lược:** vector (pgvector cosine), keyword (Postgres full-text),
  **hybrid (Reciprocal Rank Fusion)**.
- **Reranking** Cohere `rerank-v3.5` (cross-encoder trên pool hybrid).
- **Generation** grounded + citations `[n]`, từ chối khi không có trong docs.
- **Eval harness** + **golden dataset 50 item** (44 answerable + 6 negative traps),
  verify từng đáp án với docs v1.0.
- **2 cách đo metric (đủ "đúng sách"):**
  1. **LLM-judge tự viết** (`ai/eval/judge.py`) — chạy chung venv.
  2. **Ragas thật** — venv py3.12 riêng + cầu nối JSON (`ai/eval/ragas_eval.py`).
- **Files:** `ai/app/{chunking,retrieval,rerank,generation,pipeline,llm}.py`,
  `ai/eval/{metrics,judge,harness,ragas_eval}.py`,
  `ai/scripts/{ingest,ask,search,run_eval,export_for_ragas}.py`.

### Phase 2 — Agent layer
- **LangGraph ReAct agent** (`StateGraph`: agent ⇄ ToolNode).
- **3 tools:** `rag_search` (pipeline Phase 1), `calculator` (AST an toàn),
  `list_doc_topics`.
- **Guardrails:** giới hạn vòng lặp + recursion_limit, `ToolNode(handle_tool_errors)`,
  validate input, chống prompt-injection (từ chối lộ system prompt — đã verify).
- **Eval:** tool-selection accuracy đo bằng số.
- **Files:** `ai/app/{tools,agent}.py`, `ai/eval/{agent_dataset.json,agent_harness.py}`,
  `ai/scripts/{agent_ask,run_agent_eval}.py`.

### Web UI
- Trang chat: **toggle RAG ⇄ Agent**, badge tool agent đã dùng, citations clickable,
  dropdown chọn config retrieval. `web/app/page.tsx`, `web/lib/api.ts`.
- Backend: `POST /ask` (RAG) + `POST /agent` (LangGraph).

### Observability
- **Langfuse**: trace cost/latency/token từng LLM call (drop-in `langfuse.openai` cho
  Phase 1, CallbackHandler cho agent). Multi-step trace của agent đã verify.

### Deploy
- **Render** (ai): blueprint `render.yaml` (native Python, `$PORT`, health `/health`).
- **Vercel** (web): root `web/`, `NEXT_PUBLIC_API_URL` → Render.
- **Neon** (db): dùng chung dev/prod.
- **Guide:** [DEPLOY.md](DEPLOY.md).

---

## 2. Kết quả số (đo thật, không phải demo)

### Retrieval + generation eval — n=50 (LLM-judge)

| Config | hit@5 | MRR | P@5 | latency | faithfulness | relevancy | ctx-prec | ctx-recall | neg-handling |
|---|---|---|---|---|---|---|---|---|---|
| keyword | 0.386 | 0.330 | 0.298 | 429ms | 0.43 | 0.46 | 0.43 | 0.42 | 1.00 |
| baseline (vector) | 0.977 | 0.902 | 0.627 | 1422ms | 0.90 | 0.92 | 0.89 | 0.88 | 1.00 |
| hybrid (RRF) | 0.977 | 0.896 | 0.627 | 2028ms | 0.90 | 0.93 | 0.90 | 0.89 | 1.00 |
| **hybrid+rerank** | **1.000** | **0.928** | **0.727** | 3001ms | **0.92** | **0.93** | **0.92** | **0.91** | 1.00 |

→ **hybrid+rerank thắng baseline trên MỌI metric.** Đánh đổi: latency ~2× (precision/latency tradeoff).

### Ragas thật (hybrid+rerank, 44 samples)

| metric | Ragas | LLM-judge | Khớp? |
|---|---|---|---|
| faithfulness | 0.934 | 0.918 | ✓ |
| answer_relevancy | 0.823 | 0.927 | Ragas dùng embedding similarity (khác cách) |
| context_precision | 0.885 | 0.918 | ✓ |
| context_recall | 0.843 | 0.914 | ✓ tầm tương đương |

→ Hai phương pháp **corroborate** lẫn nhau (kiểm chứng độc lập).

### Agent — tool-selection (12 item)

| Metric | Giá trị |
|---|---|
| tool-selection accuracy (exact set) | **0.917** |
| required-tool recall | **1.000** |

→ docs→`rag_search`, math→`calculator`, meta→`list_doc_topics`, multi-tool 1 lượt; guardrails verify.

---

## 3. ⚠️ QUAN TRỌNG — phải làm

### Rotate API keys (bảo mật — ưu tiên #1)
Các key (OpenAI, Cohere, Langfuse) đã **lộ trong lịch sử chat** VÀ đang chạy trên **deploy public**.
Rủi ro thật: key OpenAI bị lạm dụng = **tốn tiền**.

**Cách làm:**
1. OpenAI: platform.openai.com → API keys → tạo key mới, **xoá key cũ**.
2. Cập nhật key mới ở **3 nơi**:
   - `ai/.env` (local) — `EMBEDDING_API_KEY` + `OPENROUTER_API_KEY`
   - **Render dashboard** → Environment (dán **1 dòng/value**, không kèm dòng khác)
   - (Cohere/Langfuse nếu tạo mới)
3. Verify lại pipeline còn chạy.

---

## 4. Polish tùy chọn (không gấp)

| Polish | Giá trị | Effort |
|---|---|---|
| **Fix Langfuse keys trên Render** | Có dashboard cost/latency của traffic prod (hiện 401, chỉ là tracing nên không sập app) | 5 phút, re-paste 2 key sạch |
| **Cohere key mới** | Bật lại rerank thật trên live (hiện degrade về hybrid) | Lấy trial key mới → `COHERE_API_KEY` ở local + Render |
| **Streaming UX** | Câu trả lời chảy token + hiện "đang dùng tool X" real-time (Vercel AI SDK) | Trung bình — SSE qua FastAPI + Next.js |
| **Caching** | Cache embedding + semantic cache câu hỏi lặp → giảm cost/latency | Trung bình |
| **Rate limiting + auth** | Chống lạm dụng API public (tái dùng Arcjet/Kinde) | Trung bình |
| **Mở rộng dataset 50→80+** | Số liệu generation ổn định hơn nữa | Thấp (curate thêm) |
| **Giữ Render khỏi cold-start** | Free tier ngủ sau 15' → request đầu ~60s. Cron ping `/health` mỗi 10' hoặc lên paid | Thấp |
| **Cross-encoder rerank local** | Thay Cohere bằng bge-reranker (không tốn API) | Cao — model nặng, trái ràng buộc máy yếu |

---

## 5. Chạy lại / reproduce

```bash
# AI service
cd ai
python -m venv .venv && .venv\Scripts\Activate.ps1        # Windows
pip install -r requirements.txt
cp .env.example .env        # điền DATABASE_URL + EMBEDDING_API_KEY (+ optional)
python -m scripts.init_db && python -m scripts.fetch_corpus && python -m scripts.ingest
python -m scripts.run_eval --judge        # bảng eval
python -m scripts.run_agent_eval          # tool-selection
uvicorn app.main:app --reload --port 8000

# Ragas thật (venv riêng py3.12)
py -3.12 -m venv .venv-ragas
.venv-ragas\Scripts\python -m pip install -r requirements-ragas.txt
python -m scripts.export_for_ragas
.venv-ragas\Scripts\python -m eval.ragas_eval

# Web
cd web
NODE_OPTIONS=--use-system-ca pnpm install
NODE_OPTIONS=--use-system-ca pnpm dev     # http://localhost:3000
```

---

## 6. Tóm tắt thành quả (điền số thật ở trên)

> **Agentic RAG Assistant** — *Next.js, TypeScript, Python (FastAPI), PostgreSQL+pgvector,
> LangGraph, Cohere Rerank, Ragas, Langfuse — [live](https://agentic-rag-assistant.vercel.app)*
> - Xây RAG pipeline hybrid search (pgvector + full-text qua RRF) + reranking, nâng retrieval
>   **MRR từ 0.90 (baseline) lên 0.93** trên golden dataset 50 câu; faithfulness 0.92.
> - Thiết kế eval pipeline đo retrieval + faithfulness/context-precision/recall bằng **Ragas thật
>   + LLM-judge** (corroborate nhau); track cost/latency từng request qua Langfuse.
> - Xây agent đa bước **LangGraph** tự chọn tool với guardrails (loop limit, tool-error,
>   prompt-injection); **tool-selection accuracy 0.917**.
> - Deploy production: Vercel + Render + Neon, graceful degradation (rerank lỗi → fallback hybrid).
