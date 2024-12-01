from functools import wraps
from flask import abort
from flask_login import current_user
from app.models.user import User

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return abort(401)
            if role not in current_user.has_role(role):
                return abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator