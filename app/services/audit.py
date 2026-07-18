from flask import request

from app.extensions import db
from app.models import AuditLog


def log_activity(user, action, table_name, record_id, old_values=None, new_values=None):
    entry = AuditLog(
        user_id=user.id if user is not None else None,
        action=action,
        table_name=table_name,
        record_id=str(record_id),
        old_values=old_values,
        new_values=new_values,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(entry)
    return entry
