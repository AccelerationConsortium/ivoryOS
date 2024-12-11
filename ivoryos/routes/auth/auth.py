from flask import Blueprint, redirect, url_for, flash, request, render_template, session
from flask_login import login_required, login_user, logout_user, LoginManager
import bcrypt

from ivoryos.utils.db_models import Script, User, db
from ivoryos.utils.utils import post_script_file
login_manager = LoginManager()

auth = Blueprint('auth', __name__, template_folder='templates/auth')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """
    .. :quickref: User; login user

    .. http:get:: /login

    load user login form.

    .. http:post:: /login

    :form username: username
    :form password: password
    :status 302: and then redirects to homepage
    :status 401: incorrect password, redirects to :http:get:`/ivoryos/login`
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
            session['user'] = username
            script_file = Script(author=username)
            session["script"] = script_file.as_dict()
            session['hidden_functions'], session['card_order'], session['prompt'] = {}, {}, {}
            session['autofill'] = False
            post_script_file(script_file)
            return redirect(url_for('main.index'))
        else:
            flash("Incorrect username or password")
            return redirect(url_for('auth.login')), 401
    return render_template('login.html')


@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    .. :quickref: User; signup for a new account

    .. http:get:: /signup

    load user sighup

    .. http:post:: /signup

    :form username: username
    :form password: password
    :status 302: and then redirects to :http:get:`/ivoryos/login`
    :status 409: when user already exists, redirects to :http:get:`/ivoryos/signup`
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        user = User(username, hashed)
        try:
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('auth.login'))
        except Exception:
            flash("username exists :(", "error")
            return render_template('signup.html'), 409
    return render_template('signup.html')


@auth.route("/logout")
@login_required
def logout():
    """
    .. :quickref: User; logout the user

    logout the current user, clear session info, and redirect to the login page.
    """
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))


@login_manager.user_loader
def load_user(username):
    return User(username, password=None)
