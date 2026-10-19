# Evaluation cases

`cases.json` is a small deterministic gold set for validating the SQL/data-tool layer. It checks that representative analytical queries return known values from the bundled sample dataset.

This is not an end-to-end LLM benchmark and does not claim model accuracy. End-to-end evaluation should later track answer correctness, tool-selection quality, latency, and token cost across multiple model runs.
