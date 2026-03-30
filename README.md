# Energetech Deal Confirmation Agent

Reads a deal confirmation memo, extracts structured trade data via an LLM, validates it, runs a mock credit check, and returns a combined JSON response.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your OPENAI_API_KEY
```

## Run

```bash
python main.py
```

Set `LLM_PROVIDER=ollama` and `OLLAMA_MODEL` in `.env` to run locally without an API key.

## What I'd improve with more time

- Unit tests — at minimum for validation rules and the credit-check logic
- PDF/image input support (right now it only handles plain text)
- A real credit ledger instead of stateless mock rules
- A thin FastAPI wrapper so other systems can call it over HTTP

## Notes

The agent includes a regex-based recovery pass after LLM extraction. This was necessary — even GPT-4o occasionally drops `reference` or `confirmed_by` on the first call.

## Part 2: Architecture Design

For the second part of the assessment (proposing a real-time credit check system), please see the attached [design_doc.md](./design_doc.md).
