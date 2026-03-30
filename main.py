#!/usr/bin/env python3

import os
import sys
import logging
from dotenv import load_dotenv

from src.agent import DealAgent


DEAL_MEMO = """
DEAL CONFIRMATION

Date: 18 March 2026
Reference: ET-2026-0441

Seller: Gulf Power Trading LLC
Buyer: Meridian Energy Partners FZE

Commodity: Natural Gas
Volume: 50,000 MMBtu
Delivery Period: 1 April 2026 – 30 April 2026
Delivery Point: Title Transfer at Jebel Ali Hub
Price: USD 8.40 per MMBtu
Payment Terms: Net 5 business days after delivery
Governing Law: DIFC

Confirmed by: Ahmed Al-Farsi (Gulf Power Trading LLC)
""".strip()

def setup_app_logging():
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S"
    )
    
    # Silence noisy libraries
    for lib in ["httpx", "httpcore", "openai", "urllib3"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

def main():
    load_dotenv()
    setup_app_logging()
    
    logger = logging.getLogger(__name__)

    # Default to open_ai but allow ollama overrides
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if provider == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        url = None
    else:
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    logger.info("=" * 60)
    logger.info("ENERGETECH DEAL CONFIRMATION AGENT")
    logger.info(f"Provider: {provider}  |  Model: {model}")
    logger.info("=" * 60)

    print("\nInput Deal Memo:")
    print("-" * 40)
    print(DEAL_MEMO)
    print("-" * 40)

    try:
        agent = DealAgent(provider=provider, model_name=model, base_url=url)
        result = agent.process_deal_memo(DEAL_MEMO)

        print("\n" + "=" * 60)
        print("FINAL OUTPUT")
        print("=" * 60)
        print(result.model_dump_json(indent=2))

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()