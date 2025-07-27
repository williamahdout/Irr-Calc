import unittest
import os
from app import app, db, User, Stock, Transaction

class PortfolioTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.dirname(app.config['APPLICATION_ROOT']), 'test.db')
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def register(self, username, password):
        return self.app.post('/register', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def login(self, username, password):
        return self.app.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_register_and_login(self):
        rv = self.register('testuser', 'testpassword')
        self.assertIn(b'Welcome, testuser!', rv.data)
        self.logout()
        rv = self.login('testuser', 'testpassword')
        self.assertIn(b'Welcome, testuser!', rv.data)

    def test_add_and_sell_stock(self):
        self.register('testuser', 'testpassword')
        # Mock the get_stock_price function to avoid actual API calls
        app.get_stock_price = lambda ticker: 100.0

        # Add a stock
        self.app.post('/add_stock', data=dict(
            ticker='AAPL',
            shares='10'
        ), follow_redirects=True)

        with app.app_context():
            stock = Stock.query.filter_by(ticker='AAPL').first()
            self.assertIsNotNone(stock)
            self.assertEqual(stock.shares, 10)

        # Sell some of the stock
        self.app.post('/sell_stock', data=dict(
            ticker='AAPL',
            shares='5'
        ), follow_redirects=True)

        with app.app_context():
            stock = Stock.query.filter_by(ticker='AAPL').first()
            self.assertEqual(stock.shares, 5)

            transaction = Transaction.query.filter_by(ticker='AAPL', transaction_type='sell').first()
            self.assertIsNotNone(transaction)
            self.assertEqual(transaction.shares, 5)

if __name__ == '__main__':
    unittest.main()
