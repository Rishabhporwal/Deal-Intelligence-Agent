import os
import json
import logging
import re
from typing import Any, Optional, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

from src.models import ExtractedDeal, CreditCheckResult, CreditStatus, DealResponse
from src.tools import check_credit
from src.prompts import (
    EXTRACTION_SYSTEM, 
    EXTRACTION_HUMAN,
    TOOL_INVOCATION_SYSTEM, 
    TOOL_INVOCATION_HUMAN
)

logger = logging.getLogger(__name__)

# ==============================================================================
# Graph State
# ==============================================================================
class AgentState(TypedDict):
    deal_memo: str
    extracted_deal: Optional[ExtractedDeal]
    extraction_error: Optional[str]
    validation_flags: list[str]
    credit_check_result: Optional[CreditCheckResult]
    credit_check_error: Optional[str]
    final_response: Optional[DealResponse]

# ==============================================================================
# Node: Extraction
# ==============================================================================
def _parse_json_fallback(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    for pattern in (r"```(?:json)?\s*\n?(.*?)\n?\s*```", r"```\s*\n?(.*?)\n?\s*```"):
        if m := re.search(pattern, text, re.DOTALL):
            try: return json.loads(m.group(1).strip())
            except: pass
            
    idx = text.find("{")
    if idx != -1:
        try: return json.loads(text[idx:text.rfind("}")+1])
        except: pass
        
    return None

def _sanitise_raw(data: dict) -> dict:
    string_fields = [
        "reference", "date", "seller", "buyer", "commodity",
        "delivery_start", "delivery_end", "delivery_point",
        "payment_terms", "governing_law", "confirmed_by",
    ]
    for field in string_fields:
        if field in data and isinstance(data[field], (list, dict)):
            data[field] = str(data[field])
    return data

def _recover_missing_fields(deal: ExtractedDeal, memo: str) -> ExtractedDeal:
    data = deal.model_dump()
    def _find(label):
        m = re.search(rf"^{label}[:\s]+(.+)$", memo, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else None
    
    if not data.get("reference"): data["reference"] = _find("reference")
    if not data.get("seller"): data["seller"] = _find("seller")
    if not data.get("buyer"): data["buyer"] = _find("buyer")
    if not data.get("commodity"): data["commodity"] = _find("commodity")
    if not data.get("volume_mmbtu"):
        m = re.search(r"volume[:\s]+([\d,]+)\s*mmbtu", memo, re.IGNORECASE)
        if m: data["volume_mmbtu"] = float(m.group(1).replace(",", ""))
    
    return ExtractedDeal.model_validate(data)

def create_extraction_node(llm: BaseChatModel, is_openai: bool):
    def extraction_node(state: AgentState) -> dict[str, Any]:
        memo = state["deal_memo"]
        try:
            if is_openai:
                structured_llm = llm.with_structured_output(ExtractedDeal)
                deal = structured_llm.invoke([
                    SystemMessage(content=EXTRACTION_SYSTEM),
                    HumanMessage(content=EXTRACTION_HUMAN.format(deal_memo=memo))
                ])
            else:
                response = llm.invoke([
                    SystemMessage(content=EXTRACTION_SYSTEM + "\n\nReturn plain JSON. No markdown fences."),
                    HumanMessage(content=EXTRACTION_HUMAN.format(deal_memo=memo))
                ])
                parsed = _sanitise_raw(_parse_json_fallback(response.content) or {})
                deal = ExtractedDeal.model_validate(parsed)
            
            deal = _recover_missing_fields(deal, memo)
            logger.info(f"Extracted: ref={deal.reference}, buyer={deal.buyer}, volume={deal.volume_mmbtu}")
            return {"extracted_deal": deal, "extraction_error": None}
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {"extracted_deal": None, "extraction_error": str(e)}
            
    return extraction_node

# ==============================================================================
# Node: Validation
# ==============================================================================
def validation_node(state: AgentState) -> dict[str, Any]:
    deal = state.get("extracted_deal")
    if not deal:
        return {"validation_flags": []}

    flags = []
    required = ["reference", "date", "seller", "buyer", "commodity", "volume_mmbtu", "price_usd_per_mmbtu"]
    for field in required:
        if getattr(deal, field, None) is None:
            flags.append(f"Missing required field: {field}")
            
    if deal.volume_mmbtu and deal.volume_mmbtu <= 0:
        flags.append("Volume is zero or negative")
        
    if deal.confirmed_by and deal.seller and deal.buyer:
        confirmed = deal.confirmed_by.lower()
        if deal.seller.lower() in confirmed and deal.buyer.lower() not in confirmed:
            flags.append("Deal confirmed only by seller — buyer confirmation missing")
            
    if flags:
        logger.warning(f"Validation: {len(flags)} issue(s) found")
    else:
        logger.info("Validation: clean")
        
    return {"validation_flags": flags}

# ==============================================================================
# Node: Credit Check
# ==============================================================================
def create_credit_check_node(llm: BaseChatModel, is_openai: bool):
    def credit_check_node(state: AgentState) -> dict[str, Any]:
        deal = state.get("extracted_deal")
        if not deal:
            return {"credit_check_result": None}

        counterparty = deal.buyer or "UNKNOWN"
        volume = deal.volume_mmbtu or 0.0
        
        try:
            if is_openai:
                llm_with_tools = llm.bind_tools([check_credit])
                response = llm_with_tools.invoke([
                    SystemMessage(content=TOOL_INVOCATION_SYSTEM),
                    HumanMessage(content=TOOL_INVOCATION_HUMAN.format(
                        buyer=counterparty, 
                        seller=deal.seller or "UNKNOWN", 
                        volume_mmbtu=volume
                    ))
                ])
                if hasattr(response, "tool_calls") and response.tool_calls:
                    args = response.tool_calls[0]["args"]
                    result = CreditCheckResult.model_validate(check_credit.invoke(args))
                    logger.info(f"Credit check via LLM tool: {result.status.value}")
                    return {"credit_check_result": result}
            
            # Direct invocation fallback (mainly used for Ollama or if LLM doesn't call tool)
            result = CreditCheckResult.model_validate(check_credit.invoke({
                "counterparty_name": counterparty, 
                "volume_mmbtu": volume
            }))
            logger.info(f"Direct credit check for {counterparty}: {result.status.value}")
            return {"credit_check_result": result}
            
        except Exception as e:
            logger.error(f"Credit check error: {e}")
            return {"credit_check_error": str(e)}
            
    return credit_check_node

# ==============================================================================
# Node: Assembly
# ==============================================================================
def assembly_node(state: AgentState) -> dict[str, Any]:
    deal = state.get("extracted_deal")
    flags = state.get("validation_flags", [])
    credit = state.get("credit_check_result")
    
    if not deal:
        return {"final_response": DealResponse(validation_flags=[f"EXTRACTION FAILED: {state.get('extraction_error')}"])}
        
    if not credit:
        credit = CreditCheckResult(counterparty="UNKNOWN", volume=0.0, status=CreditStatus.FLAGGED, message="Credit check skipped")
        
    response = DealResponse.from_extracted_deal(deal=deal, credit_check=credit, extra_flags=flags)
    logger.info(f"Assembled response: ref={response.reference}, {len(response.validation_flags)} flag(s)")
    return {"final_response": response}

# ==============================================================================
# DealAgent Class (Graph Compilation)
# ==============================================================================
class DealAgent:
    def __init__(self, provider: str, model_name: str, base_url: str = None):
        self.provider = provider.lower()
        self.is_openai = (self.provider == "openai")
        
        # Instantiate LLM
        if self.is_openai:
            self.llm = ChatOpenAI(model=model_name)
        else:
            self.llm = ChatOllama(model=model_name, base_url=base_url or "http://localhost:11434")
            
        self.graph = self._compile_graph()

    def _compile_graph(self):
        builder = StateGraph(AgentState)
        
        builder.add_node("extract", create_extraction_node(self.llm, self.is_openai))
        builder.add_node("validate", validation_node)
        builder.add_node("credit_check", create_credit_check_node(self.llm, self.is_openai))
        builder.add_node("assemble", assembly_node)
        
        builder.add_edge(START, "extract")
        builder.add_edge("extract", "validate")
        builder.add_edge("validate", "credit_check")
        builder.add_edge("credit_check", "assemble")
        builder.add_edge("assemble", END)

        return builder.compile()

    def process_deal_memo(self, deal_memo: str) -> DealResponse:
        logger.info(f"Processing deal memo ({len(deal_memo)} chars)")
        try:
            final_state = self.graph.invoke({"deal_memo": deal_memo})
            return final_state.get("final_response")
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            raise