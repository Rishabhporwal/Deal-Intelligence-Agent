"""Prompts used for LLM extraction and tool invocation."""

from langchain_core.prompts import ChatPromptTemplate

EXTRACTION_SYSTEM = """\
You are a trade operations analyst. Extract structured deal data from the
deal confirmation memo below with complete accuracy.

Rules:
1. Extract every field. Do not skip any.
2. "reference" → the deal reference number (e.g. "ET-2026-0441"). Look for "Reference:" in the memo.
3. "date" → the deal date in YYYY-MM-DD format. "18 March 2026" → "2026-03-18".
4. "confirmed_by" → the person AND company from the "Confirmed by:" line. Include both.
5. All dates must be YYYY-MM-DD (ISO 8601).
6. Compute total_value_usd = volume_mmbtu × price_usd_per_mmbtu.
   "50,000 MMBtu" means fifty thousand (50000), not fifty. Watch commas in numbers.
7. In validation_flags, list any issues: missing fields, anomalous values, inconsistencies,
   or if only one counterparty confirmed the deal.
8. If no issues found, return an empty list for validation_flags.
9. Use null only for fields genuinely absent from the memo.
"""

EXTRACTION_HUMAN = """\
Extract all structured deal data from this memo. Read it line by line.

Watch for:
- "Reference:" line → "reference" field
- "Date:" line → "date" field, converted to YYYY-MM-DD
- "Confirmed by:" line → "confirmed_by" field (include full name and company)
- Volume commas: "50,000 MMBtu" = volume_mmbtu of 50000
- total_value_usd = volume_mmbtu × price_usd_per_mmbtu

--- DEAL MEMO ---
{deal_memo}
--- END MEMO ---
"""

extraction_prompt = ChatPromptTemplate.from_messages([
    ("system", EXTRACTION_SYSTEM),
    ("human", EXTRACTION_HUMAN),
])


# Prompt for the credit check tool invocation step.
# Kept deliberately short — the LLM just needs to call the tool with the right args.
TOOL_INVOCATION_SYSTEM = """\
You are a deal processing agent. Call the check_credit tool with the buyer name and deal volume.
The counterparty is always the buyer — that's the side we extend credit to.
"""

TOOL_INVOCATION_HUMAN = """\
Deal:
- Buyer: {buyer}
- Seller: {seller}
- Volume: {volume_mmbtu} MMBtu

Call check_credit now.
"""

tool_invocation_prompt = ChatPromptTemplate.from_messages([
    ("system", TOOL_INVOCATION_SYSTEM),
    ("human", TOOL_INVOCATION_HUMAN),
])