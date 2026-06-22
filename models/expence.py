from models import db


class Expense(db.Model):
    __tablename__ = "expenses"

    expense_id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.group_id"), nullable=False)
    paid_by_id = db.Column(
        db.Integer,
        db.ForeignKey("group_members.member_id"),
        nullable=False,
    )
    title = db.Column(db.String(160), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    category = db.Column(db.String(50), nullable=False, default="Other")
    split_type = db.Column(db.String(20), nullable=False, default="equal")
    expense_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    group = db.relationship("Group", back_populates="expenses")
    paid_by = db.relationship("GroupMember")
    shares = db.relationship(
        "ExpenseShare",
        back_populates="expense",
        cascade="all, delete-orphan",
    )


class ExpenseShare(db.Model):
    __tablename__ = "expense_shares"
    __table_args__ = (
        db.UniqueConstraint("expense_id", "member_id", name="uq_expense_member"),
    )

    share_id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(
        db.Integer,
        db.ForeignKey("expenses.expense_id"),
        nullable=False,
    )
    member_id = db.Column(
        db.Integer,
        db.ForeignKey("group_members.member_id"),
        nullable=False,
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)

    expense = db.relationship("Expense", back_populates="shares")
    member = db.relationship("GroupMember")
