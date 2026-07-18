from flask import current_app


def is_live_configured():
    return bool(current_app.config["GRA_EFD_ENDPOINT"])


def format_efd_payload(txn):
    """Formats a completed transaction per GRA EFD API specifications."""
    return {
        "deviceNumber": current_app.config["GRA_EFD_DEVICE_NUMBER"],
        "supplierTin": current_app.config["STORE_TIN"],
        "invoiceNumber": txn.transaction_number,
        "invoiceDate": txn.created_at.isoformat(),
        "items": [
            {
                "description": item.product.name,
                "quantity": float(item.quantity),
                "unitPrice": float(item.unit_price),
                "taxRate": float(item.product.tax_rate),
                "lineTotal": float(item.line_total),
            }
            for item in txn.items
        ],
        "vatExclusiveTotal": float(txn.subtotal),
        "taxTotal": float(txn.tax_amount),
        "grandTotal": float(txn.total_amount),
        "currency": "GHS",
    }


def transmit_to_efd(txn):
    """Transmits a completed transaction to the GRA Fiscal Management System.

    Runs in demo mode (payload formatted but not transmitted, no fiscal
    verification code returned) until GRA_EFD_ENDPOINT/API_KEY are
    configured - see config.py. Only relevant for VAT-registered
    retailers above the GHS 200,000 turnover threshold; requires a
    GRA-certified EFD device registration before it can go live.
    """
    payload = format_efd_payload(txn)

    if not is_live_configured():
        return {"live": False, "payload": payload, "fiscal_code": None}

    # TODO: real GRA EFD integration
    # response = requests.post(
    #     current_app.config["GRA_EFD_ENDPOINT"],
    #     json=payload,
    #     headers={"Authorization": f"Bearer {current_app.config['GRA_EFD_API_KEY']}"},
    # )
    # return {"live": True, "payload": payload, "fiscal_code": response.json()["fiscalCode"]}
    raise NotImplementedError("Live GRA EFD integration not yet wired up - requires certified device registration")
