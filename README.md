# DataPilot Agent

DataPilot is a tool-using AI data analyst. A user asks a question about a small sales dataset; the model chooses tools, inspects results, and returns an answer with an inspectable execution trace.

This project demonstrates agent orchestration rather than retrieval-augmented generation: model-directed tool use, bounded execution, a read-only data interface, and trace visibility.

## Features

- Dataset inspection, row preview, and read-only SQL tools exposed to a chat model.
- Bounded tool-call loop that returns each tool call, arguments, outcome, and result.
- SQLite read-only authorizer that permits reads only from `sales` and rejects writes or schema operations.
- Configurable caps on tool rounds and returned rows.
- Per-query SQLite execution timeout and a total tool-call budget.
- Included sample data for a reproducible local demo.
- Unit checks for tool behavior, SQL read boundaries, and the agent tool-call loop.
- A deterministic gold set for validating representative SQL/data-tool outputs.

## Architecture

```text
Question -> model -> tool call -> read-only SQLite -> tool result -> model -> answer + execution trace
```

## Run locally

Requires Python 3.11+ and an OpenAI-compatible chat-completions endpoint with tool-calling support.

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Set provider configuration in your shell. Never commit real API keys.

```powershell
$env:LLM_BASE_URL = "https://api.openai.com/v1"
$env:LLM_API_KEY = "your-key"
$env:LLM_CHAT_MODEL = "your-tool-capable-model"
uvicorn app.main:app --reload
```

On startup the service creates `data/demo.sqlite3` from `data/sample_sales.csv` if the database is empty. API docs: `http://127.0.0.1:8000/docs`.

## Example

```json
POST /analyze
{
  "question": "Which region had the highest total revenue, and what was the total?"
}
```

The response includes an `answer` and a `trace` array so readers can inspect the tools and data behind the response.

## Run checks

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

GitHub Actions runs the unit checks and imports the API application on pushes and pull requests.
The small `evals/cases.json` set checks tool-level outputs; it is explicitly not an end-to-end LLM accuracy benchmark.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `GET` | `/dataset` | Inspect schema and row count |
| `GET` | `/dataset/preview?limit=5` | Preview sample rows |
| `POST` | `/analyze` | Ask an analysis question |

## Engineering decisions

- The model can choose among narrow tools; it receives no shell or filesystem tool.
- SQL runs through a read-only SQLite connection. An authorizer denies writes and access to tables other than `sales`.
- Tool-round and result-row caps are enforced in code, not only requested in the prompt.
- The trace is included in the API response so failures and model behavior are reviewable.

## Current scope

This is a local single-user prototype. It has no authentication, web UI, CSV upload, background jobs, or published evaluation scores. Follow-up work: CSV upload with per-session isolation, an evaluation set with answer and SQL checks, latency/token metrics, and approval gates before introducing any write-capable tools.

Do not expose this service publicly as-is. It sends the question and query results to the configured model provider.
