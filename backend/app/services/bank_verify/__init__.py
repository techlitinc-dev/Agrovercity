import os

from app.services.bank_verify.base import BankVerifyAdapter
from app.services.bank_verify.stub import StubBankVerifyAdapter

# The real penny-drop provider (Razorpay/Cashfree) lands later — routers never change.
_ADAPTERS: dict[str, type[BankVerifyAdapter]] = {"stub": StubBankVerifyAdapter}


def get_bank_verify_adapter() -> BankVerifyAdapter:
    name = os.environ.get("BANK_VERIFY_ADAPTER", "stub")
    return _ADAPTERS.get(name, StubBankVerifyAdapter)()
