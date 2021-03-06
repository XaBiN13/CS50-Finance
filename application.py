import os
import json
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

dateTimeObj = datetime.now()
timestampStr = dateTimeObj.strftime("%d-%b-%Y (%H:%M:%S)")

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    if request.method == "GET":
        price = []
        total = []
        # get cash balance
        cash_balance = (db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"]))[0]['cash']

        # get current users portfolios
        current_user_portfolio_rows = db.execute(
            "SELECT symbol, name, SUM(shares) FROM portfolio WHERE USER_id =:user_id GROUP BY symbol HAVING (SUM(shares) >0)", user_id=session["user_id"])
        length = len(current_user_portfolio_rows)
        for i in range(length):
            price.append(lookup(current_user_portfolio_rows[i]['symbol'])['price'])
            total.append(lookup(current_user_portfolio_rows[i]['symbol'])['price']*(current_user_portfolio_rows[i]['SUM(shares)']))

        # getting total share price and cash balance
        all_total = "{:,}".format(round((sum(total) + cash_balance), 2))
        return render_template("index.html", current_user_portfolio_rows=current_user_portfolio_rows, length=length, price=price, total=total,
                               all_total=all_total, cash=cash_balance)
    else:
        return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return (render_template("buy.html"))
    else:
        # error message if user inputs an invalid Stock symbol
        stock = lookup(request.form.get("symbol"))
        if stock == None:
            return apology("Invalid Symbol", 400)
        else:
            # get the balance of the current user
            cash_balance = (db.execute(
                "SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"]))[0]['cash']
            name = stock['name']
            price = stock['price']
            shares = int(request.form.get("shares"))
            total_price = price*shares
            symbol = stock['symbol']
            print(type(price), price)
            print("Cash Balance: ", cash_balance)
            print("total price: ", total_price)
            # cash balance after purchase
            if (cash_balance > total_price):
                balance_after = cash_balance-total_price
                db.execute("INSERT INTO portfolio (user_id, symbol, name, shares, price ) VALUES (:user_id, :symbol, :name, :shares, :price )",
                           user_id=session["user_id"], symbol=symbol, name=name, shares=shares, price=total_price)
                db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash=balance_after, user_id=session["user_id"])

                # insert into History for Bought items
                db.execute("INSERT INTO history (user_id, symbol, share, price, transacted ) VALUES (:user_id, :symbol, :share, :price, :transacted )",
                           user_id=session["user_id"], symbol=symbol, share=shares, price=price, transacted=str(timestampStr))
                flash("Bought!")
                return redirect("/")
            else:
                return apology("Insufficient Fund", 400)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    if request.method == "GET":
        current_user_history = db.execute(
            "SELECT symbol, share, price, transacted FROM history WHERE USER_id =:user_id", user_id=session["user_id"])
        length = len(current_user_history)
        return render_template("history.html", current_user_history=current_user_history, length=length)

    else:
        return redirect("/")

# adding fund section
@app.route("/fund", methods=["GET", "POST"])
@login_required
def fund():
    if request.method == "GET":
        return render_template("fund.html")
    if request.method == "POST":
        cash_balance = (db.execute(
            "SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"]))[0]['cash']
        balance_after = cash_balance + float(request.form.get("fund"))
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash=balance_after, user_id=session["user_id"])
        flash("Fund Added!")
        return redirect("/")
    else:
        return redirect("/")


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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
    if request.method == "GET":
        return (render_template("quote.html"))
    else:
        stock = lookup(request.form.get("symbol"))
        if stock == None:
            return apology("Invalid Symbol", 400)
        else:

            name = stock['name']
            price = stock['price']
            symbol = stock['symbol']
            return (render_template("stock.html", name=name, symbol=symbol, price=price))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return (render_template("register.html"))
    else:
        # gets the user name from the form
        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)
        # error messages if user name or password not given
        if not username:
            return apology("You must provide a user name", 403)
        # checks if user name is taken
        if len(rows) >= 1:
            return apology("Sorry the user name is taken", 403)

        if not request.form.get("password1") or not request.form.get("password2"):
            return apology("You must provide a password", 403)

        # if both passwors match hash the pasword and save it to database
        if request.form.get("password1") == request.form.get("password2"):
            hash = generate_password_hash(request.form.get("password1"))
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hash)
            return redirect("/")
        else:
            return apology("The Password must match", 403)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    current_user_portfolio_rows = db.execute(
        "SELECT symbol, name, SUM(shares) FROM portfolio WHERE USER_id =:user_id GROUP BY symbol HAVING (SUM(shares) >0)", user_id=session["user_id"])
    length = len(current_user_portfolio_rows)
    if request.method == "GET":
        return (render_template("sell.html",  current_user_portfolio_rows=current_user_portfolio_rows, length=length))
    else:
        #current_share = db.execute("SELECT SUM(shares) FROM portfolio WHERE USER_id =:user_id AND symbol =:symbol GROUP BY symbol", user_id=session["user_id"], symbol = symbol )
        shares = int(request.form.get("shares"))
        symbol = request.form.get("symbol")
        current_share = db.execute(
            "SELECT SUM(shares) FROM portfolio WHERE USER_id =:user_id AND symbol =:symbol GROUP BY symbol", user_id=session["user_id"], symbol=symbol)
        user_current_shares = current_share[0]['SUM(shares)']

        if (user_current_shares >= shares):
            cash_balance = (db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"]))[0]['cash']
            stock = lookup(symbol)
            name = stock['name']
            price = stock['price']
            total_sold_price = price*shares

            balance_after = cash_balance + total_sold_price
            db.execute("INSERT INTO portfolio (user_id, symbol, name, shares, price ) VALUES (:user_id, :symbol, :name, :shares, :price )",
                       user_id=session["user_id"], symbol=symbol, name=name, shares=-shares, price=total_sold_price)
            db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash=balance_after, user_id=session["user_id"])
            # insert into History for sold items
            db.execute("INSERT INTO history (user_id, symbol, share, price, transacted ) VALUES (:user_id, :symbol, :share, :price, :transacted )",
                       user_id=session["user_id"], symbol=symbol, share=-shares, price=price, transacted=str(timestampStr))

            # Redirect user to home page
            flash("Sold!")
            return redirect("/")
        else:
            return apology("Not too many shares")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
