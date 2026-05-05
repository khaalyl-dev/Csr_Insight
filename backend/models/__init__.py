"""
Models - all database table definitions (User, Site, CsrPlan, etc.).

Each model maps to a MySQL table. app.py imports this module so db.create_all()
creates all tables. Import models as: from models import User, Site
"""
from .user import User
from .user_permission import UserPermission
from .user_session import UserSession
from .site import Site
from .user_site import UserSite
from .category import Category
from .external_partner import ExternalPartner
from .csr_plan import CsrPlan
from .planned_activity import CsrActivity
from .realized_activity import RealizedCsr
from .csr_objective import CsrObjective
from .csr_completed_objective import CsrCompletedObjective
from .csr_attachment import CsrAttachment
from .validation import Validation
from .change_request import ChangeRequest
from .document import Document
from .notification import Notification
from .csr_snapshot import CsrSnapshot
from .chatbot_log import ChatbotLog
from .audit_log import AuditLog
from .entity_history import EntityHistory

__all__ = [
    "User",
    "UserPermission",
    "UserSession",
    "Site",
    "UserSite",
    "Category",
    "ExternalPartner",
    "CsrPlan",
    "CsrActivity",
    "RealizedCsr",
    "CsrObjective",
    "CsrCompletedObjective",
    "CsrAttachment",
    "Validation",
    "ChangeRequest",
    "Document",
    "Notification",
    "CsrSnapshot",
    "ChatbotLog",
    "AuditLog",
    "EntityHistory",
]
