import uuid

from sqlalchemy import CHAR

from core.db import db


def _uuid_default():
    return str(uuid.uuid4())


class CsrAttachment(db.Model):
    __tablename__ = "csr_attachments"

    id = db.Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, default=_uuid_default)
    activity_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        db.ForeignKey("planned_activity.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path = db.Column(db.Text, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=db.func.now())

    activity = db.relationship("CsrActivity", backref=db.backref("attachments_rows", lazy="dynamic"))
