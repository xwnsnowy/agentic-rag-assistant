# Phase 0 — Nền tảng & dữ liệu ✅ HOÀN TẤT

> Tổng kết những gì đã làm xong ở Phase 0, trước khi sang Phase 1 (RAG core + Eval).
> Tham chiếu kế hoạch gốc: [Agentic_RAG_Build_Plan.md](Agentic_RAG_Build_Plan.md).

**Mục tiêu Phase 0:** dựng khung dự án (web + ai), bật pgvector trên Postgres, chứng minh
một vòng round-trip vector (insert + cosine query) chạy được, nối Next.js ↔ FastAPI, và tải
một corpus thật sẵn sàng để ingest.

---

## Definition of Done — cả 3 đều đạt

- [x] **Insert 1 chunk có embedding vào Postgres + query cosine similarity ra kết quả.**
      → `python -m scripts.seed_chunk`: chèn document id=1, chunk id=1; query `<=>` trả về match.
- [x] **Next.js gọi được FastAPI và nhận response.**
      → Trang chủ `web/` là server component fetch `/health` + `/db/health`, hiển thị trạng thái.
- [x] **Corpus đã ở dạng raw, sẵn sàng ingest.**
      → 12 trang docs LangGraph v1.0 (~325 KB markdown) trong `ai/data/raw/` + `manifest.json`.

---

## Kiến trúc đã dựng

```
web/   Next.js 16 + TypeScript + Tailwind v4   (pnpm)   -> UI + health check tới ai/
ai/    Python 3.14 + FastAPI                            -> embeddings, DB, retrieval (sau)
        └── PostgreSQL + pgvector (Neon, ap-southeast-1) -> documents, chunks
```

Hai ngôn ngữ / hai vai trò có chủ đích: TS cho app, Python cho "bộ não AI".

---

## Đã build chi tiết

### `ai/` — FastAPI service
| File | Vai trò |
|---|---|
| `app/main.py` | FastAPI app: `GET /`, `/health` (liveness), `/db/health` (readiness) + CORS |
| `app/config.py` | Config đọc từ env (pydantic-settings) — không hardcode host/port/key |
| `app/db.py` | Kết nối psycopg3; helper `vector_literal()` format vector → text literal cast `::vector` |
| `app/embeddings.py` | Embeddings qua API OpenAI-compatible + fallback fake-embedding offline cho Phase 0 |
| `app/__init__.py` | Inject `truststore` vào SSL (dùng OS trust store) |
| `migrations/001_init.sql` | `CREATE EXTENSION vector` + bảng `documents`, `chunks`; index HNSW cosine + GIN full-text |
| `scripts/init_db.py` | Apply migration |
| `scripts/seed_chunk.py` | Insert 1 chunk + chạy cosine query (bằng chứng DoD) |
| `scripts/fetch_corpus.py` | Tải corpus docs LangGraph v1.0 |

**Schema `chunks`:** `id`, `document_id` (FK), `content`, `embedding vector(1536)`,
`metadata jsonb`, `tsv tsvector` (generated từ content — cho keyword side của hybrid search ở
Phase 1), `created_at`.

### `web/` — Next.js app
| File | Vai trò |
|---|---|
| `app/page.tsx` | Server component, fetch song song `/health` + `/db/health`, render trạng thái connected/lỗi |
| `lib/api.ts` | Base URL qua `NEXT_PUBLIC_API_URL` (deploy-aware, không hardcode localhost) |

### Database
- **Neon** (Postgres + pgvector), region `ap-southeast-1`, kết nối qua **pooled URL** (`sslmode=require`).
- Không cài Postgres local, không Docker (theo ràng buộc máy yếu trong CLAUDE.md).

### Corpus
- **Nguồn:** docs LangGraph v1.0, pin chặt ở **tag `1.0.10`** qua `llms.txt` chính thức của repo
  `langchain-ai/langgraph`.
- **Cách lấy:** với mỗi URL trong `llms.txt`, tải bản `.md` (Mintlify serve markdown sạch khi
  thêm `.md` vào URL) → giữ nguyên heading + code block.
- **Kết quả:** 12 docs / ~325 KB. Provenance đầy đủ (version, URL, byte size, thời điểm tải) ở
  `ai/data/manifest.json`.
- 2 link bỏ qua (ghi trong manifest): *API Reference* (host khác) và *Why LangGraph?* (404 bản `.md`).

---

## Quyết định kỹ thuật (để defend khi phỏng vấn)

1. **Vector truyền dạng text literal + cast `::vector`** thay vì dùng adapter pgvector-python —
   bớt một dependency, vẫn đúng và đủ nhanh cho Phase 0.
2. **Index HNSW + `vector_cosine_ops`** khớp với toán tử `<=>` (cosine distance) dùng khi query;
   GIN trên `tsv` cho keyword side của hybrid search Phase 1.
3. **Không clone repo langgraph để lấy docs** — vì ở v1.0 nội dung docs đã **rời khỏi repo**,
   chỉ còn `llms.txt` trỏ sang `docs.langchain.com`. Đã kiểm chứng trước khi viết script.
4. **Lấy bản `.md` thay vì crawl HTML** — markdown sạch, không phải strip HTML, code block không vỡ.
5. **`truststore` cho Python** = bản tương đương `--use-system-ca` của Node, vì máy có CA nội bộ
   chặn verify mặc định. Inject tự động trong `app/__init__.py`.
6. **Fake-embedding fallback** để chứng minh đường ống pgvector mà chưa tốn token API. Lưu ý:
   similarity sẽ thấp/vô nghĩa cho tới khi cắm key thật ở Phase 1.

---

## Cách chạy lại (reproduce)

```bash
# --- ai/ ---
cd ai
python -m venv .venv && .venv\Scripts\Activate.ps1     # Windows
pip install -r requirements.txt
cp .env.example .env        # điền DATABASE_URL (Neon pooled URL)

python -m scripts.init_db        # tạo extension + bảng
python -m scripts.seed_chunk     # insert + cosine query (DoD)
python -m scripts.fetch_corpus   # tải corpus LangGraph v1.0 -> data/raw/
uvicorn app.main:app --reload --port 8000

# --- web/ ---
cd web
NODE_OPTIONS=--use-system-ca pnpm install
NODE_OPTIONS=--use-system-ca pnpm dev    # http://localhost:3000
```

---

## Lưu ý môi trường (đặc thù máy này)

- **Dùng `pnpm`, không dùng npm** cho `web/`.
- **SSL/CA nội bộ:** Node/pnpm cần `NODE_OPTIONS=--use-system-ca`; Python dùng `truststore`.
- **Git:** repo riêng đã `git init` tại `D:\WorkSpace\agentic-rag-assistant` (tách khỏi repo `D:\`). Remote:
  https://github.com/xwnsnowy/agentic-rag-assistant
- **Secrets:** `ai/.env` chứa `DATABASE_URL` — đã gitignore, không commit.

---

## Chưa làm (để dành Phase 1)

- Embedding thật (`text-embedding-3-small`) — hiện đang fake; cần cắm `EMBEDDING_API_KEY`.
- Ingestion + heading-based chunking corpus vào bảng `chunks`.
- Hybrid search (pgvector + tsvector qua Reciprocal Rank Fusion), reranking.
- Generation có citations.
- Eval pipeline (golden dataset + Ragas + LLM-as-judge) — làm **song song**, không để cuối.
