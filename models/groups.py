from models import db


class Group(db.Model):
    __tablename__ = "groups"

    group_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    currency = db.Column(db.String(8), nullable=False, default="₹")
    owner_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    owner = db.relationship("User", back_populates="owned_groups")
    members = db.relationship(
        "GroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="GroupMember.created_at",
    )
    expenses = db.relationship(
        "Expense",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    settlements = db.relationship(
        "Settlement",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class GroupMember(db.Model):
    __tablename__ = "group_members"
    __table_args__ = (
        db.UniqueConstraint("group_id", "email", name="uq_group_member_email"),
    )

    member_id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.group_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    group = db.relationship("Group", back_populates="members")
    user = db.relationship("User")


class GroupInvitation(db.Model):
    __tablename__ = "group_invitations"

    invitation_id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.group_id"), nullable=False)
    invited_by_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    token = db.Column(db.String(120), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_by_id = db.Column(db.Integer, db.ForeignKey("users.user_id"))
    accepted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    group = db.relationship("Group")
    invited_by = db.relationship("User", foreign_keys=[invited_by_id])
    accepted_by = db.relationship("User", foreign_keys=[accepted_by_id])
