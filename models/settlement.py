from models import db


class Settlement(db.Model):
    __tablename__ = "settlements"

    settlement_id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.group_id"), nullable=False)
    paid_by_id = db.Column(
        db.Integer,
        db.ForeignKey("group_members.member_id"),
        nullable=False,
    )
    paid_to_id = db.Column(
        db.Integer,
        db.ForeignKey("group_members.member_id"),
        nullable=False,
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    settled_on = db.Column(db.Date, nullable=False)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    group = db.relationship("Group", back_populates="settlements")
    paid_by = db.relationship("GroupMember", foreign_keys=[paid_by_id])
    paid_to = db.relationship("GroupMember", foreign_keys=[paid_to_id])
