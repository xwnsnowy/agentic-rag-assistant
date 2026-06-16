# Agentic RAG Assistant — Kế hoạch build theo phase

> Project flagship cho hồ sơ **AI Engineer**. Mục tiêu: chứng minh chiều sâu ở tầng LLM (RAG, evaluation, agent orchestration), không chỉ "gọi API". Tận dụng nền Next.js/TypeScript/PostgreSQL sẵn có, bổ sung Python cho tầng AI/eval.

---

## Nguyên tắc xuyên suốt

- **Mỗi phase tự nó là một sản phẩm hoàn chỉnh.** Dừng ở bất kỳ phase nào vẫn có thứ để show và để viết lên CV.
- **Không sang phase sau khi phase trước chưa qua "Definition of Done" (DoD).** DoD ở đây là tiêu chí eval đo được, không phải "thấy chạy là xong".
- **Hai ngôn ngữ, hai vai trò rõ ràng:** TypeScript cho app (UI + auth + chat history), Python cho "bộ não AI" (embeddings, retrieval, agent, eval). Đây là split production thật và lấp khoảng trống Python trong CV.

## Kiến trúc tổng thể

```
[Next.js app]  ── HTTP ──>  [Python service: FastAPI]
  UI + auth                   embeddings / retrieval
  chat history                agent orchestration
  render citations            eval pipeline
        │                              │
        └──────── PostgreSQL + pgvector ┘
                  (chunks, embeddings, chat logs)
```

## Tech stack

| Tầng | Lựa chọn | Ghi chú |
|---|---|---|
| Frontend / App | Next.js, TypeScript, Tailwind, Vercel AI SDK (streaming) | Đã thành thạo, để làm UI production |
| Vector store | PostgreSQL + **pgvector** | Không phải học DB mới; ghi điểm "hiểu vector search ở tầng DB" |
| AI service | **Python + FastAPI** | Nơi đặt embeddings, retrieval, agent, eval |
| Embeddings | `text-embedding-3-small` (OpenAI) hoặc Voyage/Cohere | small là đủ tốt + rẻ cho portfolio |
| LLM | qua OpenRouter (đã biết) | Linh hoạt đổi model để so eval |
| Reranking | Cohere Rerank API hoặc cross-encoder (bge-reranker) | API nhanh hơn để bắt đầu |
| Eval | **Ragas** + LLM-as-judge tự viết | Ragas cho metric chuẩn, custom cho cái Ragas thiếu |
| Observability | **Langfuse** (self-host hoặc free tier) | Trace + cost + latency, nhìn rất pro |
| Agent | **LangGraph** (Python) | State machine rõ ràng, dễ kể chuyện orchestration |

---

## Phase 0 — Nền tảng & dữ liệu (3–5 ngày)

**Mục tiêu:** dựng khung và chọn dữ liệu thật. Đừng dùng "3 file PDF lặt vặt" — chọn một corpus đủ lớn và có chủ đề rõ (ví dụ: toàn bộ docs của một framework, một bộ tài liệu nội bộ giả lập, hoặc một codebase).

**Việc làm:**
1. Khởi tạo Postgres + bật extension `pgvector`. Thiết kế schema: bảng `documents`, `chunks` (text, embedding `vector`, metadata jsonb, tsvector cho full-text).
2. Dựng Python FastAPI service rỗng + Next.js app rỗng, nối được với nhau bằng 1 endpoint health-check.
3. Chọn và tải corpus. Ghi lại nguồn, kích thước, số tài liệu.

**Definition of Done:**
- [ ] Insert được 1 chunk có embedding vào Postgres và query cosine similarity ra kết quả.
- [ ] Next.js gọi được FastAPI và nhận response.
- [ ] Corpus đã nằm ở dạng raw, sẵn sàng để ingest.

---

## Phase 1 — RAG core + Eval (1.5–2.5 tuần) ⭐ FLAGSHIP

> Hết phase này là bạn đã có một project đủ mạnh để đưa lên CV. **Đừng vội nhảy sang Phase 2.**

**Mục tiêu:** một RAG pipeline làm tử tế, KÈM lớp đo lường. Đây là phần phân biệt người làm thật với người làm demo.

**Việc làm — đúng thứ tự:**

1. **Ingestion + chunking có suy nghĩ.** Recursive/semantic chunking thay vì cắt cứng theo ký tự. Gắn metadata (nguồn, tiêu đề, vị trí) vào mỗi chunk để sau này trích dẫn được.
2. **Retrieval cơ bản.** Embed query → cosine similarity top-k qua pgvector. Đây là baseline để so.
3. **Hybrid search.** Kết hợp semantic (pgvector) + keyword (Postgres `tsvector` full-text) rồi gộp bằng **Reciprocal Rank Fusion**.
4. **Reranking.** Đưa top-N từ hybrid qua reranker, lấy top-k cuối. Đo xem reranking có cải thiện không (sẽ thấy ở eval).
5. **Generation + Citations.** Đưa context vào LLM, bắt model trả lời CÓ trích dẫn nguồn (chunk id → render link ở UI). Citations là thứ giảm hallucination và gây ấn tượng mạnh nhất.
6. **Eval pipeline (làm song song, không để cuối).**
   - Tạo **golden dataset**: 30–50 cặp (câu hỏi + câu trả lời chuẩn + chunk đúng cần lấy).
   - Đo **retrieval**: context precision / recall, hit rate, MRR.
   - Đo **generation**: faithfulness (có bịa không), answer relevancy — dùng Ragas + LLM-as-judge.
   - Track **cost + latency** mỗi câu (qua Langfuse).
   - Chạy eval cho từng cấu hình: baseline vs hybrid vs hybrid+rerank → có bảng so sánh số liệu.

**Definition of Done:**
- [ ] Có bảng eval so sánh tối thiểu 3 cấu hình retrieval bằng số liệu thật.
- [ ] Hybrid + rerank cho retrieval accuracy cao hơn baseline (và bạn giải thích được vì sao).
- [ ] Faithfulness đo được, mọi câu trả lời đều có citation truy ngược về chunk.
- [ ] Dashboard Langfuse xem được cost + latency từng request.

**Câu nói "ăn điểm" sau phase này:** *"Tôi đo được chất lượng retrieval và biết khi nào hệ thống tệ đi — không chỉ build cho chạy."*

---

## Phase 2 — Agent layer (1.5–2 tuần)

**Mục tiêu:** nâng cấp từ "RAG app" thành "agentic system". Retrieval ở Phase 1 giờ trở thành **một tool mà agent tự quyết khi nào dùng**.

**Việc làm:**
1. **Bọc RAG thành tool.** `rag_search(query)` trả về context + citations.
2. **Thêm 1–2 tool nữa.** Ví dụ `web_search` (thông tin mới), `calculator` hoặc `db_query` (truy vấn có cấu trúc). Mỗi tool có input/output schema rõ.
3. **Orchestration với LangGraph.** Agent kiểu ReAct/state-machine: nhận câu hỏi → quyết định gọi tool nào → lặp tới khi đủ thông tin → trả lời kèm citations.
4. **Guardrails — phần quan trọng nhất, đừng bỏ:**
   - Giới hạn số vòng lặp (chống loop vô tận).
   - Xử lý lỗi tool (timeout, tool trả rác) → agent vẫn trả lời gọn gàng.
   - Validate input/output, chặn prompt injection cơ bản.
5. **(Tùy chọn ăn điểm thời sự):** expose các tool theo chuẩn **MCP**.
6. **Eval cho agent:** thêm bộ test đo tool selection accuracy (agent có chọn đúng tool không) + task success rate trên các câu hỏi multi-step.

**Definition of Done:**
- [ ] Agent tự chọn đúng tool cho ít nhất 3 loại câu hỏi khác nhau.
- [ ] Có test đo tool-selection accuracy bằng số.
- [ ] Tool fail thì agent xử lý mượt, không crash, không trả rác.
- [ ] Trace nhiều bước hiện rõ trên Langfuse (gọi tool gì, theo thứ tự nào).

**Câu nói "ăn điểm" sau phase này:** *"Tôi hiểu agent orchestration, guardrails và cách đo độ chính xác khi chọn tool — không chỉ một lần gọi API."*

---

## Phase 3 — Polish production (tùy chọn, 1 tuần)

Chỉ làm nếu còn thời gian. Mỗi mục đều tăng độ "production-ready":

- **Streaming UI** mượt (Vercel AI SDK) + hiển thị "agent đang dùng tool X".
- **Caching** embeddings + semantic cache cho câu hỏi lặp (giảm cost).
- **Rate limiting + auth** (bạn đã làm Arcjet/Kinde ở project cũ → tái sử dụng được).
- **Deploy thật:** Next.js trên Vercel, Python service trên Railway/Fly.io, Postgres managed.
- **README tử tế:** kiến trúc, bảng eval, ảnh dashboard, hướng dẫn chạy.

---

## Cách trình bày trên CV (làm sau khi xong Phase 1)

Thay phần mô tả chung chung bằng **số đo được**. Ví dụ mẫu (điền số thật của bạn):

> **Agentic RAG Assistant** — *Next.js, TypeScript, Python (FastAPI), PostgreSQL + pgvector, LangGraph, Ragas, Langfuse*
> - Xây RAG pipeline với hybrid search + reranking, nâng retrieval accuracy từ X% lên Y% so với baseline (đo trên bộ eval Z câu hỏi).
> - Thiết kế eval pipeline đo faithfulness & retrieval với Ragas + LLM-as-judge; track cost/latency qua Langfuse.
> - Xây agent đa bước (LangGraph) tự chọn tool với guardrails; tool-selection accuracy đạt W%.

Con số cụ thể đánh bại mọi từ khóa chung chung. Đó là điểm khác biệt lớn nhất giữa CV junior thường và CV được gọi phỏng vấn.

---

## Tổng thời gian ước tính

| Phase | Thời gian | Trạng thái có thể show |
|---|---|---|
| 0 | 3–5 ngày | (chưa show) |
| 1 | 1.5–2.5 tuần | ✅ RAG + Eval — đủ mạnh cho CV |
| 2 | 1.5–2 tuần | ✅ Full agentic system |
| 3 | ~1 tuần | ✅ Production-grade |

> Ước tính cho nhịp làm part-time. Bạn luôn có thứ để show từ cuối Phase 1 — không bao giờ ở trạng thái tay trắng.
