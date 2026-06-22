import secrets
import smtplib
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from email.message import EmailMessage
from functools import wraps
from urllib.parse import quote

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from models import db
from models.expence import Expense, ExpenseShare
from models.groups import Group, GroupInvitation, GroupMember
from models.user import User, VerificationCode


api_bp = Blueprint("api", __name__, url_prefix="/api")


def serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="mobile-api")


def issue_access_token(user):
    return serializer().dumps({"user_id": user.user_id}, salt="access-token")


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="Authentication required."), 401
        try:
            payload = serializer().loads(
                header.removeprefix("Bearer ").strip(),
                salt="access-token",
                max_age=60 * 60 * 24 * 30,
            )
        except (BadSignature, SignatureExpired):
            return jsonify(error="Session expired. Please log in again."), 401
        g.api_user = db.session.get(User, payload.get("user_id"))
        if not g.api_user or not g.api_user.is_verified:
            return jsonify(error="Verified account required."), 401
        return view(*args, **kwargs)

    return wrapped


def send_email_otp(user, code):
    required = ["MAIL_HOST", "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM"]
    if any(not current_app.config.get(key) for key in required):
        current_app.logger.warning("Development OTP for %s: %s", user.email, code)
        return False

    message = EmailMessage()
    message["Subject"] = "Your SplitSmart verification code"
    message["From"] = current_app.config["MAIL_FROM"]
    message["To"] = user.email
    message.set_content(
        f"Your SplitSmart verification code is {code}. "
        "It expires in 10 minutes. Do not share this code."
    )
    with smtplib.SMTP(
        current_app.config["MAIL_HOST"],
        current_app.config["MAIL_PORT"],
        timeout=15,
    ) as smtp:
        if current_app.config["MAIL_USE_TLS"]:
            smtp.starttls()
        smtp.login(
            current_app.config["MAIL_USERNAME"],
            current_app.config["MAIL_PASSWORD"],
        )
        smtp.send_message(message)
    return True


def create_and_send_otp(user):
    VerificationCode.query.filter_by(user_id=user.user_id, used_at=None).delete()
    code = f"{secrets.randbelow(1_000_000):06d}"
    verification = VerificationCode(
        user_id=user.user_id,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    verification.set_code(code)
    db.session.add(verification)
    db.session.commit()
    delivered = send_email_otp(user, code)
    return delivered, code


def as_money(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid amount.")


def user_membership(group_id, user_id):
    return GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()


@api_bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip() or None
    password = str(data.get("password", ""))
    if len(name) < 2 or "@" not in email or len(password) < 6:
        return jsonify(error="Valid name, email, and 6-character password required."), 400

    user = User.query.filter_by(email=email).first()
    if user and user.is_verified:
        return jsonify(error="This email is already registered."), 409
    if phone and User.query.filter(User.phone == phone, User.email != email).first():
        return jsonify(error="This mobile number is already registered."), 409
    if not user:
        user = User(username=name, email=email, phone=phone, is_verified=False)
        db.session.add(user)
    else:
        user.username = name
        user.phone = phone
    user.set_password(password)
    db.session.commit()

    try:
        delivered, code = create_and_send_otp(user)
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception("Unable to send registration OTP")
        return jsonify(error="We could not send the verification email. Try again."), 503

    response = {
        "message": "Verification code sent to your email.",
        "delivery": "email" if delivered else "development_log",
    }
    if not delivered and current_app.debug:
        response["development_otp"] = code
    return jsonify(response), 201


@api_bp.post("/auth/verify")
def verify():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    code = str(data.get("code", "")).strip()
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify(error="Account not found."), 404
    verification = (
        VerificationCode.query.filter_by(user_id=user.user_id, used_at=None)
        .order_by(VerificationCode.created_at.desc())
        .first()
    )
    if (
        not verification
        or verification.expires_at < datetime.utcnow()
        or not verification.check_code(code)
    ):
        return jsonify(error="Invalid or expired verification code."), 400
    verification.used_at = datetime.utcnow()
    user.is_verified = True
    db.session.commit()
    return jsonify(
        token=issue_access_token(user),
        user={"id": user.user_id, "name": user.username, "email": user.email},
    )


@api_bp.post("/auth/resend")
def resend():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(email=str(data.get("email", "")).strip().lower()).first()
    if not user or user.is_verified:
        return jsonify(error="Unverified account not found."), 404
    delivered, code = create_and_send_otp(user)
    response = {"message": "A new verification code was sent."}
    if not delivered and current_app.debug:
        response["development_otp"] = code
    return jsonify(response)


@api_bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(email=str(data.get("email", "")).strip().lower()).first()
    if not user or not user.check_password(str(data.get("password", ""))):
        return jsonify(error="Email or password is incorrect."), 401
    if not user.is_verified:
        return jsonify(error="Verify your email before logging in.", requires_verification=True), 403
    return jsonify(
        token=issue_access_token(user),
        user={"id": user.user_id, "name": user.username, "email": user.email},
    )


@api_bp.get("/groups")
@token_required
def list_groups():
    memberships = GroupMember.query.filter_by(user_id=g.api_user.user_id).all()
    return jsonify(
        groups=[
            {
                "id": membership.group.group_id,
                "name": membership.group.name,
                "description": membership.group.description,
                "currency": membership.group.currency,
                "member_count": len(membership.group.members),
                "is_admin": membership.group.owner_id == g.api_user.user_id,
            }
            for membership in memberships
        ]
    )


@api_bp.post("/groups")
@token_required
def create_group():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify(error="Group name is required."), 400
    group = Group(
        name=name,
        description=str(data.get("description", "")).strip(),
        currency=str(data.get("currency", "INR")).strip() or "INR",
        owner_id=g.api_user.user_id,
    )
    group.members.append(
        GroupMember(
            user_id=g.api_user.user_id,
            name=g.api_user.username,
            email=g.api_user.email,
        )
    )
    db.session.add(group)
    db.session.commit()
    return jsonify(id=group.group_id, name=group.name), 201


@api_bp.get("/groups/<int:group_id>")
@token_required
def group_detail(group_id):
    membership = user_membership(group_id, g.api_user.user_id)
    if not membership:
        return jsonify(error="Group not found."), 404
    group = membership.group
    return jsonify(
        group={
            "id": group.group_id,
            "name": group.name,
            "description": group.description,
            "currency": group.currency,
            "is_admin": group.owner_id == g.api_user.user_id,
            "members": [
                {"id": member.member_id, "name": member.name, "email": member.email}
                for member in group.members
            ],
            "expenses": [
                {
                    "id": expense.expense_id,
                    "title": expense.title,
                    "amount": float(expense.amount),
                    "category": expense.category,
                    "date": expense.expense_date.isoformat(),
                    "paid_by": expense.paid_by.name,
                    "split_type": expense.split_type,
                }
                for expense in sorted(
                    group.expenses,
                    key=lambda item: item.expense_date,
                    reverse=True,
                )
            ],
        }
    )


@api_bp.post("/groups/<int:group_id>/invitations")
@token_required
def invite(group_id):
    group = db.session.get(Group, group_id)
    if not group or group.owner_id != g.api_user.user_id:
        return jsonify(error="Only the group admin can invite people."), 403
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower() or None
    phone = str(data.get("phone", "")).strip() or None
    if not email and not phone:
        return jsonify(error="Email or mobile number is required."), 400

    token = secrets.token_urlsafe(32)
    invitation = GroupInvitation(
        group_id=group_id,
        invited_by_id=g.api_user.user_id,
        email=email,
        phone=phone,
        token=token,
        expires_at=datetime.utcnow() + timedelta(days=7),
    )
    db.session.add(invitation)
    db.session.commit()

    invite_url = f"{current_app.config['PUBLIC_APP_URL'].rstrip('/')}/invite/{token}"
    text = (
        f"{g.api_user.username} invited you to join {group.name} on SplitSmart. "
        f"Accept here: {invite_url}"
    )
    return jsonify(
        invitation_id=invitation.invitation_id,
        invite_url=invite_url,
        whatsapp_url=f"https://wa.me/{phone or ''}?text={quote(text)}",
        share_text=text,
        expires_at=invitation.expires_at.isoformat(),
    ), 201


@api_bp.post("/invitations/<token>/accept")
@token_required
def accept_invitation(token):
    invitation = GroupInvitation.query.filter_by(token=token).first()
    if not invitation or invitation.status != "pending":
        return jsonify(error="Invitation is invalid or already used."), 400
    if invitation.expires_at < datetime.utcnow():
        invitation.status = "expired"
        db.session.commit()
        return jsonify(error="Invitation has expired."), 400
    if invitation.email and invitation.email != g.api_user.email:
        return jsonify(error="This invitation was sent to another email address."), 403
    if invitation.phone and invitation.phone != g.api_user.phone:
        return jsonify(error="This invitation was sent to another mobile number."), 403

    membership = user_membership(invitation.group_id, g.api_user.user_id)
    if not membership:
        db.session.add(
            GroupMember(
                group_id=invitation.group_id,
                user_id=g.api_user.user_id,
                name=g.api_user.username,
                email=g.api_user.email,
            )
        )
    invitation.status = "accepted"
    invitation.accepted_by_id = g.api_user.user_id
    invitation.accepted_at = datetime.utcnow()
    db.session.commit()
    return jsonify(message="Invitation accepted.", group_id=invitation.group_id)


def split_amounts(total, split_type, shares):
    member_ids = [int(item["member_id"]) for item in shares]
    if split_type == "equal":
        cents = int(total * 100)
        base, remainder = divmod(cents, len(member_ids))
        return {
            member_id: Decimal(base + (index < remainder)) / 100
            for index, member_id in enumerate(member_ids)
        }
    values = {int(item["member_id"]): as_money(item.get("value")) for item in shares}
    if split_type == "exact" and sum(values.values()) == total:
        return values
    if split_type == "percentage" and sum(values.values()) == Decimal("100.00"):
        result = {}
        running = Decimal("0.00")
        for member_id in member_ids[:-1]:
            result[member_id] = (total * values[member_id] / 100).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )
            running += result[member_id]
        result[member_ids[-1]] = total - running
        return result
    raise ValueError("Split values do not match the selected method.")


@api_bp.post("/groups/<int:group_id>/expenses")
@token_required
def add_expense(group_id):
    membership = user_membership(group_id, g.api_user.user_id)
    if not membership:
        return jsonify(error="You are not a member of this group."), 403
    data = request.get_json(silent=True) or {}
    try:
        total = as_money(data.get("amount"))
        paid_by_id = int(data.get("paid_by_id"))
        shares = data.get("shares") or []
        if total <= 0 or not shares:
            raise ValueError("Amount and split members are required.")
        valid_ids = {member.member_id for member in membership.group.members}
        if paid_by_id not in valid_ids or any(
            int(item.get("member_id", 0)) not in valid_ids for item in shares
        ):
            raise ValueError("Every participant must be a group member.")
        amounts = split_amounts(total, str(data.get("split_type", "equal")), shares)
        expense = Expense(
            group_id=group_id,
            paid_by_id=paid_by_id,
            title=str(data.get("title", "")).strip(),
            amount=total,
            category=str(data.get("category", "Other")),
            split_type=str(data.get("split_type", "equal")),
            expense_date=date.fromisoformat(str(data.get("date", date.today().isoformat()))),
            notes=str(data.get("notes", "")).strip(),
        )
        if not expense.title:
            raise ValueError("Expense title is required.")
        expense.shares = [
            ExpenseShare(member_id=member_id, amount=amount)
            for member_id, amount in amounts.items()
        ]
        db.session.add(expense)
        db.session.commit()
        return jsonify(id=expense.expense_id, message="Expense added."), 201
    except (ValueError, TypeError) as error:
        db.session.rollback()
        return jsonify(error=str(error)), 400
