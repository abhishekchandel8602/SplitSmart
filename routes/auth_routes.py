from flask import (
    Blueprint,
    render_template
)

auth_bp = Blueprint(
    "auth",
    __name__
)

@auth_bp.route(
    "/register",
    methods=["GET"]
)
def register():

    return render_template(
        "register.html"
    )