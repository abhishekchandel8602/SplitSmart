from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from functools import wraps

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.orm import selectinload

from models import db
from models.expence import Expense, ExpenseShare
from models.groups import Group, GroupMember
from models.settlement import Settlement
from models.user import User


main_bp = Blueprint("main", __name__)
CATEGORIES = ["Food", "Travel", "Stay", "Shopping", "Entertainment", "Bills", "Other"]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def current_user():
    return db.session.get(User, session["user_id"])


def owned_group_or_404(group_id):
    group = db.session.get(Group, group_id)
    if not group or group.owner_id != session.get("user_id"):
        abort(404)
    return group


def money(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return Decimal("0.00")


def group_balances(group):
    balances = {member.member_id: Decimal("0.00") for member in group.members}
    for expense in group.expenses:
        balances[expense.paid_by_id] += money(expense.amount)
        for share in expense.shares:
            balances[share.member_id] -= money(share.amount)
    for settlement in group.settlements:
        balances[settlement.paid_by_id] += money(settlement.amount)
        balances[settlement.paid_to_id] -= money(settlement.amount)
    return balances


def suggested_payments(group, balances):
    debtors = [[mid, -amount] for mid, amount in balances.items() if amount < 0]
    creditors = [[mid, amount] for mid, amount in balances.items() if amount > 0]
    member_names = {member.member_id: member.name for member in group.members}
    suggestions = []
    debtor_index = creditor_index = 0

    while debtor_index < len(debtors) and creditor_index < len(creditors):
        amount = min(debtors[debtor_index][1], creditors[creditor_index][1])
        if amount > Decimal("0.00"):
            suggestions.append(
                {
                    "from_id": debtors[debtor_index][0],
                    "from_name": member_names[debtors[debtor_index][0]],
                    "to_id": creditors[creditor_index][0],
                    "to_name": member_names[creditors[creditor_index][0]],
                    "amount": amount,
                }
            )
        debtors[debtor_index][1] -= amount
        creditors[creditor_index][1] -= amount
        if debtors[debtor_index][1] == 0:
            debtor_index += 1
        if creditors[creditor_index][1] == 0:
            creditor_index += 1
    return suggestions


@main_bp.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    groups = (
        Group.query.filter_by(owner_id=user.user_id)
        .options(
            selectinload(Group.members),
            selectinload(Group.expenses).selectinload(Expense.shares),
            selectinload(Group.settlements),
        )
        .order_by(Group.created_at.desc())
        .all()
    )
    cards = []
    total_spend = Decimal("0.00")
    for group in groups:
        spend = sum((money(expense.amount) for expense in group.expenses), Decimal("0.00"))
        total_spend += spend
        cards.append(
            {
                "group": group,
                "spend": spend,
                "balance": sum(
                    (
                        amount
                        for member_id, amount in group_balances(group).items()
                        if next(
                            (m.user_id for m in group.members if m.member_id == member_id),
                            None,
                        )
                        == user.user_id
                    ),
                    Decimal("0.00"),
                ),
            }
        )
    return render_template("dashboard.html", user=user, cards=cards, total_spend=total_spend)


@main_bp.route("/groups", methods=["POST"])
@login_required
def create_group():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Give your group a name.", "error")
        return redirect(url_for("main.dashboard"))

    user = current_user()
    group = Group(
        name=name,
        description=request.form.get("description", "").strip(),
        currency=request.form.get("currency", "₹").strip() or "₹",
        owner_id=user.user_id,
    )
    group.members.append(GroupMember(name=user.username, email=user.email, user_id=user.user_id))
    db.session.add(group)
    db.session.commit()
    flash(f"{name} is ready. Add a few friends!", "success")
    return redirect(url_for("main.group_detail", group_id=group.group_id))


@main_bp.route("/groups/<int:group_id>")
@login_required
def group_detail(group_id):
    group = owned_group_or_404(group_id)
    balances = group_balances(group)
    expenses = sorted(group.expenses, key=lambda item: (item.expense_date, item.expense_id), reverse=True)
    return render_template(
        "group_detail.html",
        group=group,
        balances=balances,
        suggestions=suggested_payments(group, balances),
        expenses=expenses,
        categories=CATEGORIES,
        today=date.today().isoformat(),
    )


@main_bp.route("/groups/<int:group_id>/members", methods=["POST"])
@login_required
def add_member(group_id):
    group = owned_group_or_404(group_id)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower() or None
    if not name:
        flash("Friend name is required.", "error")
    elif email and any(member.email == email for member in group.members):
        flash("That friend is already in this group.", "error")
    else:
        registered_user = User.query.filter_by(email=email).first() if email else None
        group.members.append(
            GroupMember(
                name=name,
                email=email,
                user_id=registered_user.user_id if registered_user else None,
            )
        )
        db.session.commit()
        flash(f"{name} joined the group.", "success")
    return redirect(url_for("main.group_detail", group_id=group_id))


def calculate_shares(amount, split_type, member_ids, form):
    if not member_ids:
        raise ValueError("Select at least one person.")
    shares = {}
    if split_type == "equal":
        cents = int(amount * 100)
        base, remainder = divmod(cents, len(member_ids))
        for index, member_id in enumerate(member_ids):
            shares[member_id] = Decimal(base + (1 if index < remainder else 0)) / 100
    elif split_type == "percentage":
        percentages = {mid: money(form.get(f"value_{mid}", 0)) for mid in member_ids}
        if sum(percentages.values()) != Decimal("100.00"):
            raise ValueError("Percentage shares must total 100%.")
        running = Decimal("0.00")
        for member_id in member_ids[:-1]:
            shares[member_id] = (amount * percentages[member_id] / 100).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )
            running += shares[member_id]
        shares[member_ids[-1]] = amount - running
    elif split_type == "exact":
        shares = {mid: money(form.get(f"value_{mid}", 0)) for mid in member_ids}
        if sum(shares.values()) != amount:
            raise ValueError("Exact shares must add up to the expense amount.")
    else:
        raise ValueError("Choose a valid split type.")
    return shares


@main_bp.route("/groups/<int:group_id>/expenses", methods=["POST"])
@login_required
def add_expense(group_id):
    group = owned_group_or_404(group_id)
    member_lookup = {member.member_id: member for member in group.members}
    try:
        amount = money(request.form.get("amount"))
        paid_by_id = int(request.form.get("paid_by_id", 0))
        member_ids = [int(value) for value in request.form.getlist("member_ids")]
        if amount <= 0:
            raise ValueError("Expense amount must be greater than zero.")
        if paid_by_id not in member_lookup or any(mid not in member_lookup for mid in member_ids):
            raise ValueError("Select valid group members.")
        shares = calculate_shares(
            amount,
            request.form.get("split_type", "equal"),
            member_ids,
            request.form,
        )
        expense = Expense(
            group_id=group.group_id,
            paid_by_id=paid_by_id,
            title=request.form.get("title", "").strip(),
            amount=amount,
            category=request.form.get("category", "Other"),
            split_type=request.form.get("split_type", "equal"),
            expense_date=date.fromisoformat(request.form.get("expense_date", date.today().isoformat())),
            notes=request.form.get("notes", "").strip(),
        )
        if not expense.title:
            raise ValueError("Expense title is required.")
        expense.shares = [
            ExpenseShare(member_id=member_id, amount=share)
            for member_id, share in shares.items()
        ]
        db.session.add(expense)
        db.session.commit()
        flash("Expense added and balances updated.", "success")
    except (ValueError, TypeError) as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("main.group_detail", group_id=group_id))


@main_bp.route("/groups/<int:group_id>/settlements", methods=["POST"])
@login_required
def add_settlement(group_id):
    group = owned_group_or_404(group_id)
    valid_ids = {member.member_id for member in group.members}
    try:
        paid_by_id = int(request.form.get("paid_by_id", 0))
        paid_to_id = int(request.form.get("paid_to_id", 0))
        amount = money(request.form.get("amount"))
        if paid_by_id == paid_to_id or paid_by_id not in valid_ids or paid_to_id not in valid_ids:
            raise ValueError("Choose two different group members.")
        if amount <= 0:
            raise ValueError("Settlement amount must be greater than zero.")
        db.session.add(
            Settlement(
                group_id=group_id,
                paid_by_id=paid_by_id,
                paid_to_id=paid_to_id,
                amount=amount,
                settled_on=date.fromisoformat(
                    request.form.get("settled_on", date.today().isoformat())
                ),
                note=request.form.get("note", "").strip(),
            )
        )
        db.session.commit()
        flash("Payment recorded.", "success")
    except (ValueError, TypeError) as error:
        db.session.rollback()
        flash(str(error), "error")
    return redirect(url_for("main.group_detail", group_id=group_id))


@main_bp.route("/groups/<int:group_id>/analytics")
@login_required
def analytics(group_id):
    group = owned_group_or_404(group_id)
    by_category = defaultdict(Decimal)
    by_month = defaultdict(Decimal)
    paid_by = defaultdict(Decimal)
    for expense in group.expenses:
        by_category[expense.category] += money(expense.amount)
        by_month[expense.expense_date.strftime("%b %Y")] += money(expense.amount)
        paid_by[expense.paid_by.name] += money(expense.amount)

    total = sum(by_category.values(), Decimal("0.00"))
    max_category = max(by_category.values(), default=Decimal("1.00"))
    max_month = max(by_month.values(), default=Decimal("1.00"))
    return render_template(
        "analytics.html",
        group=group,
        total=total,
        by_category=sorted(by_category.items(), key=lambda item: item[1], reverse=True),
        by_month=list(by_month.items()),
        paid_by=sorted(paid_by.items(), key=lambda item: item[1], reverse=True),
        max_category=max_category,
        max_month=max_month,
    )
