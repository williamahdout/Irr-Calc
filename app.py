from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import requests
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a real secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portfolio.db'
# IMPORTANT: Replace 'YOUR_API_KEY' with your actual Alpha Vantage API key
app.config['ALPHA_VANTAGE_API_KEY'] = 'YOUR_API_KEY'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    stocks = db.relationship('Stock', backref='owner', lazy=True)
    transactions = db.relationship('Transaction', backref='owner', lazy=True)

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(5), nullable=False) # 'buy' or 'sell'
    transaction_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_stock_price(ticker):
    api_key = app.config['ALPHA_VANTAGE_API_KEY']
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey={api_key}"
    response = requests.get(url)
    data = response.json()
    price = data.get("Global Quote", {}).get("05. price")
    return float(price) if price else None

@app.route('/')
@login_required
def index():
    portfolio_value = 0
    stocks_with_prices = []
    for stock in current_user.stocks:
        price = get_stock_price(stock.ticker)
        if price:
            total_value = price * stock.shares
            portfolio_value += total_value
            stocks_with_prices.append({
                'ticker': stock.ticker,
                'shares': stock.shares,
                'price': price,
                'total_value': total_value
            })
        else:
            stocks_with_prices.append({
                'ticker': stock.ticker,
                'shares': stock.shares,
                'price': 'N/A',
                'total_value': 'N/A'
            })

    return render_template('index.html', stocks=stocks_with_prices, portfolio_value=portfolio_value)

@app.route('/add_stock', methods=['POST'])
@login_required
def add_stock():
    ticker = request.form.get('ticker')
    shares = int(request.form.get('shares'))

    # In a real app, you'd also record the purchase price and date

    # Check if the user already owns this stock
    existing_stock = Stock.query.filter_by(ticker=ticker, owner=current_user).first()

    if existing_stock:
        existing_stock.shares += shares
    else:
        new_stock = Stock(ticker=ticker, shares=shares, owner=current_user)
        db.session.add(new_stock)

    db.session.commit()

    return redirect(url_for('index'))

@app.route('/sell_stock', methods=['POST'])
@login_required
def sell_stock():
    ticker = request.form.get('ticker')
    shares_to_sell = int(request.form.get('shares'))

    stock_to_sell = Stock.query.filter_by(ticker=ticker, owner=current_user).first()

    if stock_to_sell and shares_to_sell <= stock_to_sell.shares:
        price = get_stock_price(ticker)
        if price:
            # Record the transaction
            transaction = Transaction(
                ticker=ticker,
                shares=shares_to_sell,
                price=price,
                transaction_type='sell',
                owner=current_user
            )
            db.session.add(transaction)

            # Update the stock holding
            stock_to_sell.shares -= shares_to_sell
            if stock_to_sell.shares == 0:
                db.session.delete(stock_to_sell)

            db.session.commit()
        else:
            flash('Could not retrieve stock price. Please try again later.')
    else:
        flash('Invalid sell request.')

    return redirect(url_for('index'))

@app.route('/past_trades')
@login_required
def past_trades():
    # For simplicity, this example assumes every sell transaction is a closed trade.
    # A more robust implementation would match buy and sell transactions.
    closed_trades = Transaction.query.filter_by(owner=current_user, transaction_type='sell').all()

    trades_with_pl = []
    for trade in closed_trades:
        # This is a simplified P/L calculation. A real implementation would be more complex.
        # It assumes the buy price was the price at the time of the last buy transaction.
        last_buy = Transaction.query.filter_by(owner=current_user, ticker=trade.ticker, transaction_type='buy').order_by(Transaction.transaction_date.desc()).first()
        if last_buy:
            profit_loss = (trade.price - last_buy.price) * trade.shares
            trades_with_pl.append({
                'ticker': trade.ticker,
                'shares': trade.shares,
                'sell_price': trade.price,
                'buy_price': last_buy.price,
                'profit_loss': profit_loss,
                'date': trade.transaction_date
            })

    return render_template('past_trades.html', trades=trades_with_pl)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # In a real app, you'd hash the password
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
