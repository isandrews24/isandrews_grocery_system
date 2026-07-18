from flask import current_app
from escpos.printer import Dummy


def is_live_configured():
    return bool(current_app.config["PRINTER_TYPE"])


def _get_printer():
    """Real hardware connections go here once PRINTER_TYPE is configured.

    Without a configured printer this returns a Dummy() device from
    python-escpos, which renders the exact same ESC/POS command stream
    a real thermal printer would receive but captures it in memory
    instead of sending it anywhere - useful for building/testing the
    receipt layout without hardware attached.
    """
    printer_type = current_app.config["PRINTER_TYPE"]
    if printer_type == "usb":
        from escpos.printer import Usb
        return Usb(
            int(current_app.config["PRINTER_USB_VENDOR_ID"], 16),
            int(current_app.config["PRINTER_USB_PRODUCT_ID"], 16),
        )
    if printer_type == "network":
        from escpos.printer import Network
        return Network(current_app.config["PRINTER_NETWORK_IP"])
    return Dummy()


def print_pos_receipt(txn):
    p = _get_printer()
    store_name = current_app.config["STORE_NAME"]
    store_tin = current_app.config["STORE_TIN"]

    p.set(align="center", bold=True, width=2, height=2)
    p.text(store_name.upper() + "\n")
    p.set(align="center", bold=False, width=1, height=1)
    p.text("Ghana | Prices in GHS\n")
    if store_tin:
        p.text(f"TIN: {store_tin}\n")
    p.text("-" * 32 + "\n")

    p.set(align="left")
    p.text(f"Receipt: {txn.transaction_number}\n")
    p.text(f"Date: {txn.created_at.strftime('%d/%m/%Y %H:%M')}\n")
    p.text("-" * 32 + "\n")

    for item in txn.items:
        name = item.product.name[:20]
        p.text(f"{name:<20}{float(item.quantity):>4.0f} {float(item.line_total):>6.2f}\n")

    p.text("-" * 32 + "\n")
    p.set(bold=True, width=2, height=2)
    p.text(f"TOTAL GHS {float(txn.total_amount):.2f}\n")
    p.set(bold=False, width=1, height=1)
    p.text(f"Paid via: {(txn.payment_method or '').replace('_', ' ').upper()}\n")
    p.set(align="center")
    p.text("\nThank you for shopping with us!\n")
    p.cut()

    is_live = is_live_configured()
    if is_live:
        p.cashdraw(2)
    return {"live": is_live, "raw_bytes": len(p.output) if hasattr(p, "output") else None}
