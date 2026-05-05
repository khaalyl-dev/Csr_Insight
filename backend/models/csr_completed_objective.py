import uuid

from sqlalchemy import CHAR

from core.db import db


def _uuid_default():
    return str(uuid.uuid4())


class CsrCompletedObjective(db.Model):
    __tablename__ = "csr_completed_objectives"

    id = db.Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, default=_uuid_default)
    activity_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        db.ForeignKey("planned_activity.id", ondelete="CASCADE"),
        nullable=False,
    )
    objective = db.Column(db.Text, nullable=False)
    achieved = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    activity = db.relationship("CsrActivity", backref=db.backref("completed_objectives_rows", lazy="dynamic"))
