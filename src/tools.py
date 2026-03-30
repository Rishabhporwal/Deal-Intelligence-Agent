import logging

from langchain_core.tools import tool

from src.models import CreditCheckResult, CreditStatus

logger = logging.getLogger(__name__)


@tool
def check_credit(counterparty_name: str, volume_mmbtu: float) -> dict:
    """
    Run a credit check on a counterparty for a given deal volume.

    Args:
        counterparty_name: Legal name of the counterparty (the buyer).
        volume_mmbtu: Deal volume in MMBtu.

    Returns:
        Credit check result with status (approved/flagged/rejected) and message.
    """
    logger.debug(f"check_credit: counterparty='{counterparty_name}', volume={volume_mmbtu}")

    if volume_mmbtu > 100_000:
        result = CreditCheckResult(
            counterparty=counterparty_name,
            volume=volume_mmbtu,
            status=CreditStatus.REJECTED,
            message="Exceeds single-deal limit of 100,000 MMBtu",
        )
    elif "Restricted" in counterparty_name:
        result = CreditCheckResult(
            counterparty=counterparty_name,
            volume=volume_mmbtu,
            status=CreditStatus.REJECTED,
            message="Counterparty on restricted list",
        )
    elif volume_mmbtu > 60_000:
        result = CreditCheckResult(
            counterparty=counterparty_name,
            volume=volume_mmbtu,
            status=CreditStatus.FLAGGED,
            message="Requires senior approval — volume exceeds 60,000 MMBtu",
        )
    else:
        result = CreditCheckResult(
            counterparty=counterparty_name,
            volume=volume_mmbtu,
            status=CreditStatus.APPROVED,
            message="Credit check passed",
        )

    log_fn = logger.info if result.status == CreditStatus.APPROVED else logger.warning
    log_fn(f"Credit check {result.status.value.upper()} for '{counterparty_name}': {result.message}")

    return result.model_dump()