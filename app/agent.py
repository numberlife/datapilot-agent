from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from app.data import inspect_dataset, preview_rows, run_readonly_query

TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "inspect_dataset", "description": "Inspect the sales table schema and row count.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "preview_rows", "description": "Preview a few rows from the sales table.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "additionalProperties": False}}},
    {"type": "function", "function": {"name": "run_readonly_query", "description": "Run one read-only SQL query against the sales table. Only this table can be read.", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "A single SELECT or WITH query using the sales table."}}, "required": ["query"], "additionalProperties": False}}},
]


def _config() -> tuple[str, str, str]:
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    api_key, model = os.getenv("LLM_API_KEY", ""), os.getenv("LLM_CHAT_MODEL", "")
    if not api_key or not model:
        raise RuntimeError("Set LLM_API_KEY and LLM_CHAT_MODEL before using the agent.")
    return base_url, api_key, model


def _post_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Model API request failed: {exc}") from exc


def _run_tool(name: str, raw_arguments: str) -> Any:
    arguments = json.loads(raw_arguments or "{}")
    if name == "inspect_dataset":
        return inspect_dataset()
    if name == "preview_rows":
        return preview_rows(arguments.get("limit", 5))
    if name == "run_readonly_query":
        return run_readonly_query(arguments["query"], int(os.getenv("MAX_ROWS", "100")))
    raise ValueError(f"Unknown tool: {name}")


def analyze(question: str) -> dict[str, Any]:
    base_url, api_key, model = _config()
    try:
        max_rounds = max(1, min(int(os.getenv("MAX_TOOL_ROUNDS", "5")), 10))
    except ValueError:
        max_rounds = 5
    try:
        max_tool_calls = max(1, min(int(os.getenv("MAX_TOOL_CALLS", "12")), 30))
    except ValueError:
        max_tool_calls = 12
    tool_calls_used = 0
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "You are DataPilot, a tool-using data analyst. Inspect data before assumptions. Use SQL tools for calculations. Explain the method and cite concrete values from tool outputs. Never claim a tool succeeded if it returned an error. Tools are read-only; do not ask for secrets or invent data. Answer in the user's language."},
        {"role": "user", "content": question},
    ]
    trace: list[dict[str, Any]] = []
    for _round in range(max_rounds):
        if tool_calls_used >= max_tool_calls:
            break
        response = _post_json(f"{base_url}/chat/completions", api_key,
            {"model": model, "messages": messages, "tools": TOOL_DEFINITIONS, "tool_choice": "auto", "temperature": 0.1})
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Model response did not match the expected chat-completions format.") from exc
        calls = message.get("tool_calls") or []
        if not calls:
            return {"answer": message.get("content") or "The model returned an empty response.", "trace": trace}
        messages.append(message)
        for call in calls:
            function = call.get("function", {})
            name, arguments = function.get("name", ""), function.get("arguments", "{}")
            if tool_calls_used >= max_tool_calls:
                error = "Tool-call budget reached. No further tools were executed."
                output = json.dumps({"error": error}, ensure_ascii=False)
                trace.append({"tool": name, "arguments": arguments, "status": "blocked", "error": error})
            else:
                tool_calls_used += 1
                try:
                    result = _run_tool(name, arguments)
                    output = json.dumps(result, ensure_ascii=False)
                    trace.append({"tool": name, "arguments": json.loads(arguments or "{}"), "status": "ok", "result": result})
                except Exception as exc:
                    output = json.dumps({"error": str(exc)}, ensure_ascii=False)
                    trace.append({"tool": name, "arguments": arguments, "status": "error", "error": str(exc)})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": output})
    messages.append({"role": "user", "content": "Give your best answer using only the tool results already collected. State limitations clearly."})
    final = _post_json(f"{base_url}/chat/completions", api_key, {"model": model, "messages": messages, "temperature": 0.1})
    answer = final.get("choices", [{}])[0].get("message", {}).get("content") or "The agent reached its tool-call limit before producing an answer."
    return {"answer": answer, "trace": trace, "tool_round_limit_reached": True}
