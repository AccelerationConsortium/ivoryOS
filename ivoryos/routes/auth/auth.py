from flask import Blueprint, redirect, url_for, flash, request, render_template, session
from flask_login import login_required, login_user, logout_user, LoginManager, current_user
import bcrypt
from sqlalchemy_utils.types import password

from ivoryos.utils.db_models import Script, User, db
from ivoryos.utils.utils import post_script_file
login_manager = LoginManager()
# from flask import g

auth = Blueprint('auth', __name__, template_folder='templates')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """
    .. :quickref: User; login user

    .. http:get:: /auth/login

    load user login form.

    .. http:post:: /auth/login

    :form username: username
    :form password: password
    :status 302: and then redirects to homepage
    :status 401: incorrect password, redirects to :http:get:`/ivoryos/auth/login`
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # session.query(User, User.name).all()
        user = db.session.query(User).filter(User.username == username).first()
        input_password = password.encode('utf-8')
        # if user and bcrypt.checkpw(input_password, user.hashPassword.encode('utf-8')):
        if user and bcrypt.checkpw(input_password, user.hashPassword):
            # password.encode("utf-8")
            # user = User(username, password.encode("utf-8"))
            login_user(user)
            # g.user = user
            # session['user'] = username
            script_file = Script(author=username)
            session["script"] = script_file.as_dict()
            session['hidden_functions'], session['card_order'], session['prompt'] = {}, {}, {}
            session['autofill'] = False
            post_script_file(script_file)
            return redirect(url_for('main.index'))
        else:
            flash("Incorrect username or password")
            return redirect(url_for('auth.login'))
    return render_template('login.html')


@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    .. :quickref: User; signup for a new account

    .. http:get:: /auth/signup

    load user sighup

    .. http:post:: /auth/signup

    :form username: username
    :form password: password
    :status 302: and then redirects to :http:get:`/ivoryos/auth/login`
    :status 409: when user already exists, redirects to :http:get:`/ivoryos/auth/signup`
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Query the database to see if the user already exists.
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            flash("User already exists :(", "error")
            return render_template('signup.html'), 409
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user = User(username, hashed)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('auth.login'))
    return render_template('signup.html')

@auth.route("/change-password", methods=['GET', 'POST'])
@login_required
def change_password():
    """
    .. :quickref: User; change password

    .. http:get:: /auth/change-password

    .. http:post:: /auth/change-password

    change password
    """
    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        # confirm_password = request.form.get("confirm_password")
        user = User.query.filter_by(username=current_user.get_id()).first()
        if not bcrypt.checkpw(old_password.encode('utf-8'), user.hashPassword):
            flash("Incorrect password")
            return redirect(url_for("auth.change_password"))
        user.hashPassword = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        db.session.commit()
        return redirect(url_for("main.index"))
    return render_template("change_password.html")

@auth.route("/logout")
@login_required
def logout():
    """
    .. :quickref: User; logout the user

    .. http:get:: /auth/logout

    logout the current user, clear session info, and redirect to the login page.
    """
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))