import unittest
from datetime import datetime, timezone
from bot import PaperWallet, Transaction

class TestPaperWallet(unittest.TestCase):
	def setUp(self):
		self.wallet = PaperWallet(initial_usdt=1000.0)

	def test_initial_balance(self):
		self.assertEqual(self.wallet.usdt_balance, 1000.0)
		self.assertEqual(self.wallet.crypto_balance('SOL/USDT'), 0.0)
		self.assertEqual(len(self.wallet.history), 0)

	def test_successful_buy(self):
		tx = self.wallet.buy(symbol='SOL/USDT', price=100.0, amount_usdt=200.0)
		self.assertIsNotNone(tx)
		self.assertEqual(self.wallet.usdt_balance, 800.0)
		self.assertAlmostEqual(self.wallet.crypto_balance('SOL/USDT'), 2.0)
		self.assertEqual(len(self.wallet.history), 1)
		self.assertEqual(tx.side, 'BUY')

	def test_buy_insufficient_funds_capped(self):
		tx = self.wallet.buy(symbol='SOL/USDT', price=100.0, amount_usdt=1500.0)
		self.assertIsNotNone(tx)
		self.assertEqual(self.wallet.usdt_balance, 0.0)
		self.assertAlmostEqual(self.wallet.crypto_balance('SOL/USDT'), 10.0)

	def test_buy_negative_or_zero_amount(self):
		tx = self.wallet.buy(symbol='SOL/USDT', price=100.0, amount_usdt=0.0)
		self.assertIsNone(tx)
		tx_neg = self.wallet.buy(symbol='SOL/USDT', price=100.0, amount_usdt=-50.0)
		self.assertIsNone(tx_neg)

	def test_successful_sell(self):
		self.wallet.buy(symbol='SOL/USDT', price=100.0, amount_usdt=500.0)
		tx = self.wallet.sell(symbol='SOL/USDT', price=150.0, amount_crypto=2.5)
		self.assertIsNotNone(tx)
		self.assertEqual(self.wallet.usdt_balance, 500.0 + (2.5 * 150.0))
		self.assertAlmostEqual(self.wallet.crypto_balance('SOL/USDT'), 2.5)
		self.assertEqual(len(self.wallet.history), 2)
		self.assertEqual(tx.side, 'SELL')

	def test_sell_insufficient_holdings_capped(self):
		self.wallet.buy(symbol='SOL/USDT', price=100.0, amount_usdt=200.0)  # 2 SOL
		tx = self.wallet.sell(symbol='SOL/USDT', price=100.0, amount_crypto=5.0)
		self.assertIsNotNone(tx)
		self.assertAlmostEqual(self.wallet.crypto_balance('SOL/USDT'), 0.0)
		self.assertEqual(self.wallet.usdt_balance, 1000.0)

if __name__ == '__main__':
	unittest.main()
