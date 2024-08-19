import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    bought = db.execute("SELECT symbol, shares FROM owned WHERE user_id = ? ORDER BY symbol", session["user_id"])
    cash = user_row[0]["cash"]
    total = cash

    for i in bought:
        currentstock = lookup(i["symbol"])
        i["name"] = currentstock["name"]
        i["price"] = currentstock["price"]
        i["total"] = currentstock["price"] * int(i["shares"])
        total = total + (int(i["shares"]) * currentstock["price"])

    return render_template("index.html", cash=cash, bought = bought, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        try:
            numshares = int(request.form.get("shares"))
            if numshares <= 0:
                return apology("Cannot buy negative or zero shares", 400)
        except ValueError:
            return apology("Invalid shares", 400)
        except TypeError:
            return apology("must provide no of shares to sell", 400)

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("must provide symbol", 403)

        symbol=symbol.upper()
        details = lookup(symbol)

        if not details:
            return apology("symbol does not exist", 400)

        user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]

        buyingamount = numshares * details["price"]

        if (buyingamount > user_cash):
            return apology("Can't Afford", 400)

        else:
            exists = db.execute("SELECT * FROM owned WHERE symbol = ? and user_id = ?", symbol, session["user_id"])

            if len(exists) == 0:
                db.execute("INSERT INTO owned (user_id, symbol, shares) VALUES(?, ?, ?)", session["user_id"], symbol, numshares)
            else:
                db.execute("UPDATE owned SET shares = shares + ? WHERE symbol = ? AND user_id = ?", numshares, symbol, session["user_id"])

            db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", buyingamount, session["user_id"])
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time_of_transact) VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP)",
                session["user_id"], symbol, numshares, details["price"])

            flash("Bought!")
            return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT symbol, shares, price, time_of_transact FROM transactions WHERE user_id = ? order by time_of_transact", session["user_id"])
    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        flash("Login Successful!")
        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        symbol = request.form.get("symbol")

        if not symbol:
            return apology("must provide symbol", 400)

        symbol = symbol.upper()
        details = lookup(symbol)

        if not details:
            return apology("Invalid Symbol", 400)

        else:
            return render_template("quoted.html",
             name = details["name"], symbol = details["symbol"], price=usd(details["price"]))

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 400)

        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must provide confirmation for password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation do not match", 400)

        usernm = request.form.get("username")
        passwd = request.form.get("password")

        rows = db.execute("SELECT * FROM users WHERE username = ?", usernm)

        if len(rows) > 0:
            return apology("username is already taken", 400)

        else:
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",usernm, generate_password_hash(passwd))

        rows = db.execute("SELECT * FROM users WHERE username = ?", usernm)

        session["user_id"] = rows[0]["id"]

        flash("Registered!")

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        try:
            numshares = int(request.form.get("shares"))
            if numshares < 0:
                return apology("Cannot sell negative shares", 400)
        except ValueError:
            return apology("Invalid shares", 400)
        except TypeError:
            return apology("must provide no of shares to sell", 400)

        symbol = request.form.get("symbol")
        details = lookup(symbol)

        if not details:
            return apology("symbol does not exist", 400)

        owned = db.execute("SELECT shares FROM owned WHERE user_id = ? AND symbol = ?", session["user_id"], symbol)
        ownedshares = owned[0]["shares"]

        if (numshares == 0):
            return apology("Shares must be positive", 400)

        if (numshares > ownedshares):
            return apology("Too many shares", 400)

        else:
            sellingamount = numshares * details["price"]
            if (numshares == ownedshares):
                db.execute("DELETE FROM owned WHERE symbol = ? AND user_id = ?", symbol, session["user_id"])
            else:
                db.execute("UPDATE owned SET shares = shares - ? WHERE symbol = ? AND user_id = ?", numshares, symbol, session["user_id"])

            db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", sellingamount, session["user_id"])
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time_of_transact) VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP)",
                session["user_id"], symbol, -numshares, details["price"])

            flash("Sold!")
            return redirect("/")


    else:
        owned = db.execute("SELECT symbol FROM owned WHERE user_id = ?", session["user_id"])
        options = []
        for i in owned:
            options.append(i["symbol"])
        return render_template("sell.html", selectoption = options)

# Personal touches ------------------------------------------------

@app.route("/changepasswd", methods=["GET", "POST"])
@login_required
def changepasswd():

    if request.method == "POST":

        if not request.form.get("curpasswd"):
            return apology("must provide your current password", 403)

        elif not request.form.get("newpasswd"):
            return apology("must provide new password", 403)

        elif not request.form.get("confirmpasswd"):
            return apology("must provide confirmation for new password", 403)

        user_row = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])
        cur_passwd = user_row[0]["hash"]

        if not check_password_hash(cur_passwd, request.form.get("curpasswd")):
            return apology("current password does not match", 403)

        elif request.form.get("newpasswd") != request.form.get("confirmpasswd"):
            return apology("new password and confirmation do not match", 403)

        else:
            newpass = generate_password_hash(request.form.get("newpasswd"))
            db.execute("UPDATE users SET hash = ? WHERE id = ?", newpass, session["user_id"])

        flash("Password changed successfully!")
        return redirect("/")

    else:
        return render_template("changepasswd.html")

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():

    if request.method == "POST":

        try:
            amount = float(request.form.get("amount"))
        except ValueError:
            return apology("Invalid amount", 403)

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", amount, session["user_id"])

        flash("Deposit successful!")
        return redirect("/")

    else:
        return render_template("deposit.html")

@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():

    if request.method == "POST":

        try:
            amount = float(request.form.get("amount"))
        except ValueError:
            return apology("Invalid amount", 403)

        user_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        user_cash = user_row[0]["cash"]

        if amount > user_cash:
            return apology("Not enough money in account", 400)

        else:
            db.execute("UPDATE users SET cash = cash - ? WHERE id = ?", amount, session["user_id"])

        flash("Withdrawal successful!")
        return redirect("/")

    else:
        return render_template("withdraw.html")