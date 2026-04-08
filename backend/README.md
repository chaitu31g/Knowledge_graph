# CircuitAI Backend

This folder contains the Google Colab backend for CircuitAI.

## Files

| File | Purpose |
|---|---|
| `circuit_ai_colab.ipynb` | **Start here** — Upload to Colab and run cells in order |
| `requirements.txt` | All Python dependencies (installed in Cell 2) |
| `main.py` | FastAPI server with `/health`, `/process`, `/chat` endpoints |
| `model_loader.py` | Singleton loader for Qwen2.5-VL-7B-Instruct (4-bit) |
| `pdf_parser.py` | PDF → image → vision LLM → Markdown pipeline |
| `rag_engine.py` | ChromaDB storage + BGE-M3 embeddings + FlashRank reranking |

## How to Run

1. Upload the **entire `backend/` folder** contents to a Colab session (or clone the repo).
2. Set runtime to **T4 or L4 GPU**.
3. Run `circuit_ai_colab.ipynb` cells top to bottom.
4. Copy the `trycloudflare.com` URL printed in Cell 4.
5. Paste it into the **Connection** field in the local `client/` React frontend.

## API Endpoints

### `GET /health`
Returns `{ "status": "ok", "model": "..." }` — used by the frontend to verify connectivity.

### `POST /process`
- **Body**: `multipart/form-data` with `file` = PDF upload
- **Response**: `{ "status": "success", "message": "...", "chunks_stored": N }`

### `POST /chat`
- **Body**: `{ "query": "string" }`
- **Response**: `{ "response": "markdown string", "specs": { "Vgs": "...", "Id": "...", "Rdson": "..." } }`
