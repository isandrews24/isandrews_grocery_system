from flask import Blueprint, jsonify

from app.models import Product

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@api_bp.route("/products")
def products():
    items = Product.query.filter_by(is_active=True).all()
    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "unit_price": float(p.unit_price),
            "in_stock_qty": p.in_stock_qty,
        }
        for p in items
    ])
