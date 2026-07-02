"""Compatibility imports for auth routes now defined in app.py.

The Flask routes live in app.py. Importing them here keeps old imports from
breaking without registering duplicate endpoints.
"""

from app import ensure_user_columns
from app import forgot
from app import register_with_security
from app import reset_password

__all__ = [
    'ensure_user_columns',
    'forgot',
    'register_with_security',
    'reset_password',
]
