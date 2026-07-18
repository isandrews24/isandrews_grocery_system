from flask import current_app


def calculate_tax_breakdown(price_inclusive, quantity=1, is_taxable=True):
    """GRA-compliant VAT/NHIL/GetFund breakdown on a VAT-inclusive price."""
    line_total = float(price_inclusive) * float(quantity)

    if not is_taxable:
        return {
            "vat_exclusive": round(line_total, 2),
            "vat_amount": 0.0,
            "nhil": 0.0,
            "getfund": 0.0,
            "total_tax": 0.0,
            "line_total": round(line_total, 2),
        }

    vat_rate = current_app.config["VAT_RATE"] / 100
    nhil_rate = current_app.config["NHIL_RATE"] / 100
    getfund_rate = current_app.config["GETFUND_RATE"] / 100

    vat_exclusive = line_total / (1 + vat_rate)
    vat_amount = line_total - vat_exclusive
    nhil = vat_exclusive * nhil_rate
    getfund = vat_exclusive * getfund_rate

    return {
        "vat_exclusive": round(vat_exclusive, 2),
        "vat_amount": round(vat_amount, 2),
        "nhil": round(nhil, 2),
        "getfund": round(getfund, 2),
        "total_tax": round(vat_amount + nhil + getfund, 2),
        "line_total": round(line_total, 2),
    }


def totals_for_cart(items):
    """items: list of dicts with unit_price, quantity, is_taxable."""
    subtotal_incl = 0.0
    total_tax = 0.0
    for item in items:
        breakdown = calculate_tax_breakdown(item["unit_price"], item["quantity"], item.get("is_taxable", True))
        subtotal_incl += breakdown["line_total"]
        total_tax += breakdown["total_tax"]
    return {
        "subtotal": round(subtotal_incl - total_tax, 2),
        "tax": round(total_tax, 2),
        "total": round(subtotal_incl, 2),
    }
