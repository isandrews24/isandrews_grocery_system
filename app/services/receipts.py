from io import BytesIO

from flask import current_app
from flask_mail import Message
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.extensions import mail


def _draw_header(p, y, receipt_number):
    store_name = current_app.config["STORE_NAME"]
    store_tin = current_app.config["STORE_TIN"]

    p.setFont("Helvetica-Bold", 16)
    p.drawString(20 * mm, y, store_name)
    y -= 7 * mm
    p.setFont("Helvetica", 9)
    p.drawString(20 * mm, y, "Ghana  |  Prices in GHS")
    y -= 5 * mm
    if store_tin:
        p.drawString(20 * mm, y, f"TIN: {store_tin}")
        y -= 5 * mm
    p.drawString(20 * mm, y, f"Receipt: {receipt_number}")
    y -= 8 * mm
    p.line(20 * mm, y, 190 * mm, y)
    y -= 8 * mm
    return y


def _draw_line_items(p, y, lines):
    p.setFont("Helvetica-Bold", 9)
    p.drawString(20 * mm, y, "Item")
    p.drawString(130 * mm, y, "Qty")
    p.drawString(150 * mm, y, "Price")
    p.drawString(175 * mm, y, "Total")
    y -= 5 * mm
    p.setFont("Helvetica", 9)
    for name, qty, unit_price, line_total in lines:
        p.drawString(20 * mm, y, name[:45])
        p.drawRightString(140 * mm, y, f"{qty:g}")
        p.drawRightString(165 * mm, y, f"{unit_price:,.2f}")
        p.drawRightString(190 * mm, y, f"{line_total:,.2f}")
        y -= 5 * mm
    y -= 3 * mm
    p.line(20 * mm, y, 190 * mm, y)
    y -= 8 * mm
    return y


def _draw_totals(p, y, subtotal, vat, nhil, getfund, discount, total):
    def row(label, value, bold=False):
        nonlocal y
        p.setFont("Helvetica-Bold" if bold else "Helvetica", 10 if bold else 9)
        p.drawString(130 * mm, y, label)
        p.drawRightString(190 * mm, y, f"GHS {value:,.2f}")
        y -= 6 * mm

    row("Subtotal (excl. VAT)", subtotal)
    row("VAT (standard rate)", vat)
    row("NHIL", nhil)
    row("GetFund Levy", getfund)
    if discount:
        row("Discount", -discount)
    y -= 2 * mm
    p.line(130 * mm, y, 190 * mm, y)
    y -= 6 * mm
    row("TOTAL", total, bold=True)
    return y


def generate_pos_receipt_pdf(txn):
    buf = BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)
    y = 280 * mm

    y = _draw_header(p, y, txn.transaction_number)

    lines = [
        (item.product.name, float(item.quantity), float(item.unit_price), float(item.line_total))
        for item in txn.items
    ]
    y = _draw_line_items(p, y, lines)

    total_incl = float(txn.subtotal) + float(txn.tax_amount)
    vat_rate = current_app.config["VAT_RATE"] / 100
    nhil_rate = current_app.config["NHIL_RATE"] / 100
    getfund_rate = current_app.config["GETFUND_RATE"] / 100
    denom = vat_rate + nhil_rate + getfund_rate
    vat = float(txn.tax_amount) * (vat_rate / denom) if denom else 0
    nhil = float(txn.tax_amount) * (nhil_rate / denom) if denom else 0
    getfund = float(txn.tax_amount) * (getfund_rate / denom) if denom else 0

    y = _draw_totals(p, y, float(txn.subtotal), vat, nhil, getfund, float(txn.discount_amount or 0), float(txn.total_amount))

    y -= 6 * mm
    p.setFont("Helvetica", 9)
    p.drawString(20 * mm, y, f"Paid via: {(txn.payment_method or '').replace('_', ' ').upper()}")
    y -= 10 * mm
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(20 * mm, y, "Thank you for shopping with us. Goods once sold are not returnable without this receipt.")

    p.showPage()
    p.save()
    buf.seek(0)
    return buf


def generate_online_order_receipt_pdf(order):
    buf = BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)
    y = 280 * mm

    y = _draw_header(p, y, order.order_number)

    lines = [
        (item.product.name, float(item.quantity), float(item.unit_price), float(item.line_total))
        for item in order.items
    ]
    y = _draw_line_items(p, y, lines)

    vat_rate = current_app.config["VAT_RATE"] / 100
    nhil_rate = current_app.config["NHIL_RATE"] / 100
    getfund_rate = current_app.config["GETFUND_RATE"] / 100
    denom = vat_rate + nhil_rate + getfund_rate
    vat = float(order.tax_amount) * (vat_rate / denom) if denom else 0
    nhil = float(order.tax_amount) * (nhil_rate / denom) if denom else 0
    getfund = float(order.tax_amount) * (getfund_rate / denom) if denom else 0

    y = _draw_totals(p, y, float(order.subtotal), vat, nhil, getfund, 0, float(order.subtotal) + float(order.tax_amount))

    if float(order.delivery_fee or 0):
        p.setFont("Helvetica", 9)
        p.drawString(130 * mm, y, "Delivery fee")
        p.drawRightString(190 * mm, y, f"GHS {float(order.delivery_fee):,.2f}")
        y -= 6 * mm
        p.setFont("Helvetica-Bold", 10)
        p.drawString(130 * mm, y, "GRAND TOTAL")
        p.drawRightString(190 * mm, y, f"GHS {float(order.total_amount):,.2f}")
        y -= 6 * mm

    y -= 6 * mm
    p.setFont("Helvetica", 9)
    p.drawString(20 * mm, y, f"Delivery: {order.delivery_method.replace('_', ' ')}")
    y -= 10 * mm
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(20 * mm, y, "Thank you for shopping with us.")

    p.showPage()
    p.save()
    buf.seek(0)
    return buf


def send_receipt_email(to_email, receipt_number, pdf_buffer):
    """Sends the PDF receipt as an email attachment.

    Runs in suppressed mode (no real send attempted) until MAIL_USERNAME
    is configured with real SMTP credentials - see config.py.
    """
    msg = Message(
        subject=f"Your receipt {receipt_number} - {current_app.config['STORE_NAME']}",
        recipients=[to_email],
        body=f"Thank you for your purchase. Your receipt {receipt_number} is attached.",
    )
    msg.attach(f"{receipt_number}.pdf", "application/pdf", pdf_buffer.getvalue())
    mail.send(msg)
    return not current_app.config["MAIL_SUPPRESS_SEND"]
