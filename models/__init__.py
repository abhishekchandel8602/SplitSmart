from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User, VerificationCode
from models.groups import Group, GroupMember, GroupInvitation
from models.expence import Expense, ExpenseShare
from models.settlement import Settlement
