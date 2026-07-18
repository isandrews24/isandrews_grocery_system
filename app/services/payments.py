import uuid

from flask import current_app

PROVIDER_LABELS = {
    "mtn_momo": "MTN MoMo",
    "vodafone_cash": "Vodafone Cash",
    "airteltigo_money": "AirtelTigo Money",
    "paystack": "Card (Paystack)",
    "cash": "Cash",
}


def is_live_configured(provider):
    if provider == "mtn_momo":
        return bool(current_app.config.get("MTN_MOMO_API_KEY"))
    if provider == "vodafone_cash":
        return bool(current_app.config.get("VODAFONE_API_KEY"))
    if provider == "paystack":
        return bool(current_app.config.get("PAYSTACK_SECRET_KEY"))
    return False


def initiate_payment(provider, amount, phone_number=None, reference=None):
    """Trigger a payment request.

    Real MTN MoMo / Vodafone Cash / Paystack calls go here once credentials
    are configured (see config.py). Without credentials the system runs in
    demo mode: it creates a pending reference exactly like a real gateway
    would, so the rest of the checkout/POS flow can be built and tested
    against it. Swap in the real requests.post(...) calls when API keys
    are issued.
    """
    ref = reference or str(uuid.uuid4())[:8].upper()

    if provider == "cash":
        return {"status": "completed", "reference": ref, "demo_mode": False}

    if not is_live_configured(provider):
        return {
            "status": "pending",
            "reference": ref,
            "demo_mode": True,
            "message": f"Demo mode: USSD prompt simulated for {PROVIDER_LABELS.get(provider, provider)}",
        }

    # TODO: real gateway integration
    # if provider == "mtn_momo": call MTN MoMo Collections requesttopay API
    # if provider == "vodafone_cash": call Vodafone Cash merchant API
    # if provider == "paystack": call Paystack Charge API with mobile_money object
    raise NotImplementedError(f"Live integration for {provider} not yet wired up")
