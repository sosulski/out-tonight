# Out Tonight: find something to do tonight, check the weather, save events you like.
# Programming in Python: Flask, Postgres, Flask-Login, and two APIs.

import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

import db
import apis

app = Flask(__name__)

# The secret key signs the login cookie. It lives in Replit Secrets.
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("Add FLASK_SECRET_KEY in Tools > Secrets")

# Create the database tables the first time the app runs
db.create_tables()


# ---------- Flask-Login setup ----------

login_manager = LoginManager(app)
login_manager.login_view = "login"  # where @login_required sends visitors
login_manager.login_message = "Log in to see that page."


class User(UserMixin):
    """The logged-in person. UserMixin adds what Flask-Login needs."""
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login calls this on every page to find out who is logged in."""
    row = db.get_user_by_id(int(user_id))
    return User(row) if row else None


# ---------- Pages anyone can see ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/help")
def help_page():
    return render_template("help.html")


# ---------- Sign up, log in, log out ----------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        error = None
        if len(username) < 3 or not username.replace("_", "").isalnum():
            error = "Usernames need at least 3 letters, numbers, or underscores."
        elif len(password) < 8:
            error = "Passwords need at least 8 characters."
        elif password != confirm:
            error = "The two passwords don't match."
        elif db.get_user_by_username(username):
            error = "That username is taken. Try another."

        if error:
            return render_template("signup.html", error=error, username=username)

        # Never store the password itself: store a scrambled "hash" of it
        user_id = db.create_user(username, generate_password_hash(password))
        login_user(User(db.get_user_by_id(user_id)))
        flash("Welcome to Out Tonight! Set your home city to get started.")
        return redirect(url_for("profile"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = db.get_user_by_username(username)
        if row and check_password_hash(row["password_hash"], password):
            login_user(User(row))
            # Go back to the page they wanted, if it's one of ours
            next_page = request.args.get("next", "")
            if not next_page.startswith("/") or next_page.startswith("//"):
                next_page = url_for("dashboard")
            return redirect(next_page)
        return render_template("login.html", error="Wrong username or password.",
                               username=username)
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You're logged out. See you next time!")
    return redirect(url_for("home"))


# ---------- Dashboard: weather + events ----------

@app.route("/dashboard")
@login_required
def dashboard():
    profile = db.get_profile(current_user.id)
    # Search box first; otherwise use the home city from the profile
    city = request.args.get("city", "").strip() or (profile["home_city"] or "")

    weather = weather_error = events = events_error = None
    if city:
        weather, weather_error = apis.fetch_weather(city)
        events, events_error = apis.fetch_events(city, profile["favorite_category"] or "")

    return render_template("dashboard.html", profile=profile, city=city,
                           weather=weather, weather_error=weather_error,
                           events=events, events_error=events_error,
                           saved_ids=db.get_saved_event_ids(current_user.id))


# ---------- Profile ----------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        home_city = request.form.get("home_city", "").strip()
        favorite_category = request.form.get("favorite_category", "")
        bio = request.form.get("bio", "").strip()

        if home_city and "," not in home_city:
            flash("Enter your home city with a state, like Chicago, IL.")
        else:
            if favorite_category not in apis.CATEGORIES:
                favorite_category = ""  # "Any" event type
            db.update_profile(current_user.id, display_name, home_city,
                              favorite_category, bio)
            flash("Profile saved.")
        return redirect(url_for("profile"))

    return render_template("profile.html",
                           profile=db.get_profile(current_user.id),
                           saved=db.get_saved_events(current_user.id),
                           categories=apis.CATEGORIES)


# ---------- The star: save and unsave events ----------

@app.route("/save", methods=["POST"])
@login_required
def save():
    url = request.form.get("url", "")
    if not url.startswith("https://"):
        url = ""
    db.save_event(current_user.id, request.form["event_id"], request.form["name"],
                  url, request.form.get("date", ""), request.form.get("venue", ""))
    return redirect(url_for("dashboard", city=request.form.get("city", "")))


@app.route("/unsave", methods=["POST"])
@login_required
def unsave():
    db.unsave_event(current_user.id, request.form["event_id"])
    # Go back to the page the star was on
    if request.form.get("back") == "profile":
        return redirect(url_for("profile"))
    return redirect(url_for("dashboard", city=request.form.get("city", "")))


if __name__ == "__main__":
    # host="0.0.0.0" lets Replit show your app in the preview pane
    app.run(host="0.0.0.0", port=5000, debug=True)
