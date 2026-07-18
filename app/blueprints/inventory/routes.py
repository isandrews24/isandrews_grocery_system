import random
import string
from datetime import datetime, date
from urllib.parse import quote

from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import current_user

from app.extensions import db
from app.models import (
    Product, Category, Inventory, Supplier, PurchaseOrder, PurchaseOrderItem,
    StockTake, StockTakeItem, Location, StockTransfer,
)
from app.blueprints.pos.routes import roles_required
from app.services.audit import log_activity
from app.services.qr import generate_qr_png


def _default_location():
    return Location.query.filter_by(is_default=True).first()

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory", template_folder="../../templates/inventory")

MANAGER_ROLES = ("admin", "superadmin", "inventory_manager")


# ---------- Categories ----------

@inventory_bp.route("/categories", methods=["GET", "POST"])
@roles_required(*MANAGER_ROLES)
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            cat = Category(name=name)
            db.session.add(cat)
            db.session.flush()
            log_activity(current_user, "CREATE", "categories", cat.id, new_values={"name": name})
            db.session.commit()
            flash(f"Category '{name}' added.", "success")
        return redirect(url_for("inventory.categories"))

    all_categories = Category.query.order_by(Category.name).all()
    return render_template("inventory/categories.html", categories=all_categories)


@inventory_bp.route("/categories/<int:category_id>/toggle", methods=["POST"])
@roles_required(*MANAGER_ROLES)
def toggle_category(category_id):
    cat = Category.query.get_or_404(category_id)
    cat.is_active = not cat.is_active
    log_activity(current_user, "UPDATE", "categories", cat.id, new_values={"is_active": cat.is_active})
    db.session.commit()
    return redirect(url_for("inventory.categories"))


# ---------- Products ----------

@inventory_bp.route("/products")
@roles_required(*MANAGER_ROLES)
def products():
    all_products = Product.query.order_by(Product.name).all()
    return render_template("inventory/products.html", products=all_products)


@inventory_bp.route("/products/new", methods=["GET", "POST"])
@roles_required(*MANAGER_ROLES)
def new_product():
    if request.method == "POST":
        product = _save_product_form(Product())
        db.session.add(product)
        db.session.flush()
        db.session.add(Inventory(
            product_id=product.id,
            location_id=_default_location().id,
            quantity_on_hand=request.form.get("quantity_on_hand", 0, type=float),
            reorder_level=request.form.get("reorder_level", 5, type=float),
            reorder_quantity=request.form.get("reorder_quantity", 20, type=float),
        ))
        log_activity(current_user, "CREATE", "products", product.id, new_values={"name": product.name, "sku": product.sku})
        db.session.commit()
        flash(f"Product '{product.name}' created.", "success")
        return redirect(url_for("inventory.products"))

    categories_list = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return render_template("inventory/product_form.html", product=None, categories=categories_list)


@inventory_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@roles_required(*MANAGER_ROLES)
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        old_price = float(product.unit_price)
        _save_product_form(product)
        if product.inventory:
            product.inventory.quantity_on_hand = request.form.get("quantity_on_hand", 0, type=float)
            product.inventory.reorder_level = request.form.get("reorder_level", 5, type=float)
            product.inventory.reorder_quantity = request.form.get("reorder_quantity", 20, type=float)

        log_activity(
            current_user, "UPDATE", "products", product.id,
            old_values={"unit_price": old_price}, new_values={"unit_price": float(product.unit_price)},
        )
        db.session.commit()
        flash(f"Product '{product.name}' updated.", "success")
        return redirect(url_for("inventory.products"))

    categories_list = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    return render_template("inventory/product_form.html", product=product, categories=categories_list)


@inventory_bp.route("/products/<int:product_id>/qr.png")
@roles_required(*MANAGER_ROLES)
def product_qr(product_id):
    product = Product.query.get_or_404(product_id)
    url = url_for("storefront.product_detail", product_id=product.id, _external=True)
    buf = generate_qr_png(url)
    return send_file(buf, mimetype="image/png")


@inventory_bp.route("/products/<int:product_id>/label")
@roles_required(*MANAGER_ROLES)
def product_label(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("inventory/product_label.html", product=product)


@inventory_bp.route("/products/<int:product_id>/toggle", methods=["POST"])
@roles_required(*MANAGER_ROLES)
def toggle_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    log_activity(current_user, "UPDATE", "products", product.id, new_values={"is_active": product.is_active})
    db.session.commit()
    flash(f"Product '{product.name}' {'activated' if product.is_active else 'deactivated'}.", "success")
    return redirect(url_for("inventory.products"))


def _save_product_form(product):
    product.name = request.form.get("name", "").strip()
    product.sku = request.form.get("sku", "").strip()
    product.barcode_number = request.form.get("barcode_number", "").strip() or None
    product.category_id = request.form.get("category_id", type=int) or None
    product.brand = request.form.get("brand", "").strip() or None
    product.unit_price = request.form.get("unit_price", 0, type=float)
    product.cost_price = request.form.get("cost_price", 0, type=float)
    product.tax_rate = request.form.get("tax_rate", 15.0, type=float)
    product.is_taxable = request.form.get("is_taxable") == "on"
    product.unit_of_measure = request.form.get("unit_of_measure", "each").strip() or "each"

    image_url = request.form.get("image_url", "").strip()
    product.image_url = image_url or f"https://placehold.co/400x400/5c6b85/ffffff?text={quote(product.name)}"
    return product


# ---------- Suppliers ----------

@inventory_bp.route("/suppliers", methods=["GET", "POST"])
@roles_required(*MANAGER_ROLES)
def suppliers():
    if request.method == "POST":
        supplier = Supplier(
            name=request.form.get("name", "").strip(),
            contact_person=request.form.get("contact_person", "").strip() or None,
            phone=request.form.get("phone", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            ghana_tin=request.form.get("ghana_tin", "").strip() or None,
            payment_terms=request.form.get("payment_terms", "").strip() or None,
        )
        db.session.add(supplier)
        db.session.flush()
        log_activity(current_user, "CREATE", "suppliers", supplier.id, new_values={"name": supplier.name})
        db.session.commit()
        flash(f"Supplier '{supplier.name}' added.", "success")
        return redirect(url_for("inventory.suppliers"))

    all_suppliers = Supplier.query.order_by(Supplier.name).all()
    return render_template("inventory/suppliers.html", suppliers=all_suppliers)


@inventory_bp.route("/suppliers/<int:supplier_id>/toggle", methods=["POST"])
@roles_required(*MANAGER_ROLES)
def toggle_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    supplier.is_active = not supplier.is_active
    log_activity(current_user, "UPDATE", "suppliers", supplier.id, new_values={"is_active": supplier.is_active})
    db.session.commit()
    return redirect(url_for("inventory.suppliers"))


# ---------- Purchase orders ----------

def _po_number():
    return "PO-" + datetime.utcnow().strftime("%Y%m%d") + "-" + "".join(random.choices(string.digits, k=4))


@inventory_bp.route("/purchase-orders")
@roles_required(*MANAGER_ROLES)
def purchase_orders():
    pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    return render_template("inventory/purchase_orders.html", purchase_orders=pos)


@inventory_bp.route("/purchase-orders/new", methods=["GET", "POST"])
@roles_required(*MANAGER_ROLES)
def new_purchase_order():
    if request.method == "POST":
        supplier_id = request.form.get("supplier_id", type=int)
        product_ids = request.form.getlist("product_id")
        quantities = request.form.getlist("quantity")
        unit_costs = request.form.getlist("unit_cost")

        po = PurchaseOrder(supplier_id=supplier_id, po_number=_po_number(), status="draft", created_by=current_user.id)
        db.session.add(po)
        db.session.flush()

        total = 0
        for pid, qty, cost in zip(product_ids, quantities, unit_costs):
            if not pid or not qty:
                continue
            qty_f = float(qty)
            cost_f = float(cost or 0)
            db.session.add(PurchaseOrderItem(purchase_order_id=po.id, product_id=int(pid), quantity_ordered=qty_f, unit_cost=cost_f))
            total += qty_f * cost_f

        po.total_amount = round(total, 2)
        log_activity(current_user, "CREATE", "purchase_orders", po.id, new_values={"po_number": po.po_number, "total": po.total_amount})
        db.session.commit()
        flash(f"Purchase order {po.po_number} created as draft.", "success")
        return redirect(url_for("inventory.purchase_orders"))

    all_suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    all_products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    return render_template("inventory/purchase_order_form.html", suppliers=all_suppliers, products=all_products)


@inventory_bp.route("/purchase-orders/<int:po_id>/send", methods=["POST"])
@roles_required(*MANAGER_ROLES)
def send_purchase_order(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)
    if po.status == "draft":
        po.status = "sent"
        log_activity(current_user, "UPDATE", "purchase_orders", po.id, new_values={"status": "sent"})
        db.session.commit()
        flash(f"Purchase order {po.po_number} marked as sent to supplier.", "success")
    return redirect(url_for("inventory.purchase_orders"))


@inventory_bp.route("/purchase-orders/<int:po_id>/receive", methods=["GET", "POST"])
@roles_required(*MANAGER_ROLES)
def receive_purchase_order(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)

    if request.method == "POST":
        any_received = False
        for item in po.items:
            qty_key = f"received_{item.id}"
            received_qty = request.form.get(qty_key, 0, type=float)
            if received_qty > 0:
                item.quantity_received = float(item.quantity_received or 0) + received_qty
                if item.product.inventory:
                    item.product.inventory.quantity_on_hand = float(item.product.inventory.quantity_on_hand) + received_qty
                any_received = True

        if any_received:
            fully_received = all(float(i.quantity_received or 0) >= float(i.quantity_ordered) for i in po.items)
            po.status = "received" if fully_received else "partial"
            po.received_at = datetime.utcnow()
            log_activity(current_user, "UPDATE", "purchase_orders", po.id, new_values={"status": po.status})
            db.session.commit()
            flash(f"Goods received against {po.po_number}. Inventory updated.", "success")
        return redirect(url_for("inventory.purchase_orders"))

    return render_template("inventory/purchase_order_receive.html", po=po)


# ---------- Stock take ----------

@inventory_bp.route("/stock-takes")
@roles_required(*MANAGER_ROLES)
def stock_takes():
    takes = StockTake.query.order_by(StockTake.created_at.desc()).all()
    return render_template("inventory/stock_takes.html", stock_takes=takes)


@inventory_bp.route("/stock-takes/new", methods=["POST"])
@roles_required(*MANAGER_ROLES)
def new_stock_take():
    scheduled = request.form.get("scheduled_date") or date.today().isoformat()
    take = StockTake(scheduled_date=date.fromisoformat(scheduled), created_by=current_user.id)
    db.session.add(take)
    db.session.flush()

    for product in Product.query.filter_by(is_active=True).all():
        expected = float(product.inventory.quantity_on_hand) if product.inventory else 0
        db.session.add(StockTakeItem(stock_take_id=take.id, product_id=product.id, expected_quantity=expected))

    log_activity(current_user, "CREATE", "stock_takes", take.id, new_values={"scheduled_date": scheduled})
    db.session.commit()
    flash("Stock take scheduled. Count sheet generated for all active products.", "success")
    return redirect(url_for("inventory.count_stock_take", stock_take_id=take.id))


@inventory_bp.route("/stock-takes/<int:stock_take_id>/count", methods=["GET", "POST"])
@roles_required(*MANAGER_ROLES)
def count_stock_take(stock_take_id):
    take = StockTake.query.get_or_404(stock_take_id)

    if request.method == "POST":
        for item in take.items:
            key = f"count_{item.id}"
            value = request.form.get(key, "")
            if value != "":
                item.physical_quantity = float(value)
        take.status = "review"
        db.session.commit()
        flash("Counts saved. Ready for manager review.", "success")
        return redirect(url_for("inventory.review_stock_take", stock_take_id=take.id))

    return render_template("inventory/stock_take_count.html", take=take)


@inventory_bp.route("/stock-takes/<int:stock_take_id>/review")
@roles_required(*MANAGER_ROLES)
def review_stock_take(stock_take_id):
    take = StockTake.query.get_or_404(stock_take_id)
    return render_template("inventory/stock_take_review.html", take=take)


@inventory_bp.route("/stock-takes/<int:stock_take_id>/approve", methods=["POST"])
@roles_required("admin", "superadmin")
def approve_stock_take(stock_take_id):
    take = StockTake.query.get_or_404(stock_take_id)

    for item in take.items:
        if item.physical_quantity is not None and item.product.inventory:
            item.product.inventory.quantity_on_hand = item.physical_quantity

    take.status = "approved"
    take.approved_by = current_user.id
    take.approved_at = datetime.utcnow()

    log_activity(current_user, "UPDATE", "stock_takes", take.id, new_values={"status": "approved"})
    db.session.commit()
    flash("Stock take approved. Inventory levels adjusted to match physical counts.", "success")
    return redirect(url_for("inventory.stock_takes"))


# ---------- Locations ----------

@inventory_bp.route("/locations", methods=["GET", "POST"])
@roles_required(*MANAGER_ROLES)
def locations():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip() or None
        if name:
            location = Location(name=name, address=address)
            db.session.add(location)
            db.session.flush()

            # Seed a zero-stock inventory row for every existing product at the new location
            for product in Product.query.all():
                db.session.add(Inventory(product_id=product.id, location_id=location.id, quantity_on_hand=0))

            log_activity(current_user, "CREATE", "locations", location.id, new_values={"name": name})
            db.session.commit()
            flash(f"Location '{name}' added.", "success")
        return redirect(url_for("inventory.locations"))

    all_locations = Location.query.order_by(Location.name).all()
    return render_template("inventory/locations.html", locations=all_locations)


@inventory_bp.route("/locations/<int:location_id>/toggle", methods=["POST"])
@roles_required(*MANAGER_ROLES)
def toggle_location(location_id):
    location = Location.query.get_or_404(location_id)
    if location.is_default:
        flash("The default location can't be deactivated.", "warning")
        return redirect(url_for("inventory.locations"))
    location.is_active = not location.is_active
    log_activity(current_user, "UPDATE", "locations", location.id, new_values={"is_active": location.is_active})
    db.session.commit()
    return redirect(url_for("inventory.locations"))


# ---------- Stock transfers ----------

@inventory_bp.route("/transfers", methods=["GET", "POST"])
@roles_required(*MANAGER_ROLES)
def transfers():
    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        from_location_id = request.form.get("from_location_id", type=int)
        to_location_id = request.form.get("to_location_id", type=int)
        quantity = request.form.get("quantity", 0, type=float)

        if from_location_id == to_location_id:
            flash("Source and destination locations must be different.", "danger")
            return redirect(url_for("inventory.transfers"))

        source_inv = Inventory.query.filter_by(product_id=product_id, location_id=from_location_id).first()
        if not source_inv or float(source_inv.quantity_on_hand) < quantity:
            flash("Not enough stock at the source location for this transfer.", "danger")
            return redirect(url_for("inventory.transfers"))

        dest_inv = Inventory.query.filter_by(product_id=product_id, location_id=to_location_id).first()
        if not dest_inv:
            dest_inv = Inventory(product_id=product_id, location_id=to_location_id, quantity_on_hand=0)
            db.session.add(dest_inv)

        source_inv.quantity_on_hand = float(source_inv.quantity_on_hand) - quantity
        dest_inv.quantity_on_hand = float(dest_inv.quantity_on_hand) + quantity

        transfer = StockTransfer(
            product_id=product_id, from_location_id=from_location_id, to_location_id=to_location_id,
            quantity=quantity, created_by=current_user.id,
        )
        db.session.add(transfer)
        db.session.flush()

        log_activity(
            current_user, "CREATE", "stock_transfers", transfer.id,
            new_values={"product_id": product_id, "from": from_location_id, "to": to_location_id, "quantity": quantity},
        )
        db.session.commit()
        flash("Stock transferred.", "success")
        return redirect(url_for("inventory.transfers"))

    all_locations = Location.query.filter_by(is_active=True).order_by(Location.name).all()
    all_products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    recent_transfers = StockTransfer.query.order_by(StockTransfer.created_at.desc()).limit(20).all()
    return render_template(
        "inventory/transfers.html", locations=all_locations, products=all_products, transfers=recent_transfers,
    )


@inventory_bp.route("/products/<int:product_id>/stock")
@roles_required(*MANAGER_ROLES)
def product_stock(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template("inventory/product_stock.html", product=product)
