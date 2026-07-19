from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="cashier")
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20))
    is_active_user = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.is_active_user

    def has_role(self, *roles):
        return self.role in roles


class StaffInvite(db.Model):
    __tablename__ = "staff_invites"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="cashier")
    token = db.Column(db.String(64), unique=True, nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)

    invited_by_user = db.relationship("User")

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @property
    def is_pending(self):
        return not self.accepted_at and not self.is_expired


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, nullable=False, default=False)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    children = db.relationship("Category", backref=db.backref("parent", remote_side=[id]))
    products = db.relationship("Product", backref="category", lazy=True)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    brand = db.Column(db.String(100))
    barcode_number = db.Column(db.String(50), unique=True, index=True)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    cost_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    tax_rate = db.Column(db.Numeric(5, 2), nullable=False, default=15.0)
    is_taxable = db.Column(db.Boolean, default=True)
    unit_of_measure = db.Column(db.String(30), nullable=False, default="each")
    image_url = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inventories = db.relationship("Inventory", backref="product", lazy=True)

    @property
    def inventory(self):
        """Inventory row at the default (Main Store) location.

        Single-location flows (POS, storefront, stock-take, PO receiving)
        read/write through this instead of juggling location_id everywhere.
        """
        return next((inv for inv in self.inventories if inv.location.is_default), None)

    @property
    def in_stock_qty(self):
        return sum(float(inv.quantity_on_hand) for inv in self.inventories)

    @property
    def average_rating(self):
        if not self.reviews:
            return None
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)

    @property
    def review_count(self):
        return len(self.reviews)


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    reviewer_name = db.Column(db.String(150), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product", backref=db.backref("reviews", cascade="all, delete-orphan"))


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    address = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    inventories = db.relationship("Inventory", backref="location", lazy=True)


class Inventory(db.Model):
    __tablename__ = "inventory"
    __table_args__ = (db.UniqueConstraint("product_id", "location_id", name="uq_inventory_product_location"),)

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    quantity_on_hand = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    quantity_reserved = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    reorder_level = db.Column(db.Numeric(12, 3), nullable=False, default=5)
    reorder_quantity = db.Column(db.Numeric(12, 3), nullable=False, default=20)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StockTransfer(db.Model):
    __tablename__ = "stock_transfers"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    from_location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    to_location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product")
    from_location = db.relationship("Location", foreign_keys=[from_location_id])
    to_location = db.relationship("Location", foreign_keys=[to_location_id])
    created_by_user = db.relationship("User")


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), unique=True, index=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    loyalty_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    password_hash = db.Column(db.String(255))
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    phone_verified = db.Column(db.Boolean, nullable=False, default=False)
    email_otp_code = db.Column(db.String(6))
    email_otp_expires_at = db.Column(db.DateTime)
    phone_otp_code = db.Column(db.String(6))
    phone_otp_expires_at = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)

    @property
    def is_fully_verified(self):
        return self.email_verified and self.phone_verified


class PosSession(db.Model):
    __tablename__ = "pos_sessions"

    id = db.Column(db.Integer, primary_key=True)
    cashier_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    terminal_id = db.Column(db.String(50), nullable=False)
    opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    opening_float = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    closing_float = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="open")

    cashier = db.relationship("User")
    transactions = db.relationship("Transaction", backref="session", lazy=True)


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("pos_sessions.id"), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    transaction_number = db.Column(db.String(30), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    subtotal = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    discount_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    payment_method = db.Column(db.String(50), nullable=True)
    source = db.Column(db.String(20), nullable=False, default="pos")
    table_label = db.Column(db.String(50), nullable=True)
    voided_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    void_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("TransactionItem", backref="transaction", cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="transaction", cascade="all, delete-orphan")
    customer = db.relationship("Customer")
    voided_by_user = db.relationship("User", foreign_keys=[voided_by])


class TransactionItem(db.Model):
    __tablename__ = "transaction_items"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    discount_percent = db.Column(db.Numeric(5, 2), default=0)
    tax_amount = db.Column(db.Numeric(12, 2), default=0)
    line_total = db.Column(db.Numeric(14, 2), nullable=False)

    product = db.relationship("Product")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    online_order_id = db.Column(db.Integer, db.ForeignKey("online_orders.id"), nullable=True)
    payment_method = db.Column(db.String(30), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    reference_number = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")
    processed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OnlineOrder(db.Model):
    __tablename__ = "online_orders"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    order_number = db.Column(db.String(30), unique=True, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="pending")
    delivery_method = db.Column(db.String(20), nullable=False, default="click_and_collect")
    delivery_address = db.Column(db.Text, nullable=True)
    delivery_region = db.Column(db.String(100), nullable=True)
    delivery_fee = db.Column(db.Numeric(10, 2), default=0)
    subtotal = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    payment_method = db.Column(db.String(30), nullable=True)
    payment_status = db.Column(db.String(20), nullable=False, default="pending")
    notes = db.Column(db.Text, nullable=True)
    picked_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    picked_at = db.Column(db.DateTime, nullable=True)
    placed_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship("Customer")
    items = db.relationship("OnlineOrderItem", backref="order", cascade="all, delete-orphan")
    picked_by_user = db.relationship("User")

    @property
    def is_fully_picked(self):
        return bool(self.items) and all(float(i.quantity_picked) >= float(i.quantity) for i in self.items)

    @property
    def pick_progress(self):
        return f"{sum(1 for i in self.items if float(i.quantity_picked) >= float(i.quantity))}/{len(self.items)}"


class OnlineOrderItem(db.Model):
    __tablename__ = "online_order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("online_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    quantity_picked = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    line_total = db.Column(db.Numeric(14, 2), nullable=False)

    product = db.relationship("Product")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    table_name = db.Column(db.String(100), nullable=False)
    record_id = db.Column(db.String(50), nullable=False)
    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    ghana_tin = db.Column(db.String(20))
    payment_terms = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)

    purchase_orders = db.relationship("PurchaseOrder", backref="supplier", lazy=True)


class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    po_number = db.Column(db.String(30), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft")
    total_amount = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    currency = db.Column(db.String(3), default="GHS")
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    received_at = db.Column(db.DateTime, nullable=True)

    items = db.relationship("PurchaseOrderItem", backref="purchase_order", cascade="all, delete-orphan")
    created_by_user = db.relationship("User")


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity_ordered = db.Column(db.Numeric(12, 3), nullable=False)
    quantity_received = db.Column(db.Numeric(12, 3), default=0)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)

    product = db.relationship("Product")

    @property
    def total_cost(self):
        return round(float(self.quantity_ordered) * float(self.unit_cost), 2)


class StockTake(db.Model):
    __tablename__ = "stock_takes"

    id = db.Column(db.Integer, primary_key=True)
    scheduled_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="scheduled")
    is_locked = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("StockTakeItem", backref="stock_take", cascade="all, delete-orphan")
    created_by_user = db.relationship("User", foreign_keys=[created_by])
    approved_by_user = db.relationship("User", foreign_keys=[approved_by])


class StockTakeItem(db.Model):
    __tablename__ = "stock_take_items"

    id = db.Column(db.Integer, primary_key=True)
    stock_take_id = db.Column(db.Integer, db.ForeignKey("stock_takes.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    expected_quantity = db.Column(db.Numeric(12, 3), nullable=False)
    physical_quantity = db.Column(db.Numeric(12, 3), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    product = db.relationship("Product")

    @property
    def variance(self):
        if self.physical_quantity is None:
            return None
        return round(float(self.physical_quantity) - float(self.expected_quantity), 3)
