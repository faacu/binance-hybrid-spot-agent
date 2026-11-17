import unittest
import numpy as np
from bot import IndicatorEngine

class TestIndicatorEngine(unittest.TestCase):
	def test_sma_calculation(self):
		prices = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
		result = IndicatorEngine.sma(prices, period=3)
		# (30 + 40 + 50) / 3 = 40.0
		self.assertAlmostEqual(result, 40.0)

	def test_sma_insufficient_data(self):
		prices = np.array([10.0, 20.0])
		result = IndicatorEngine.sma(prices, period=5)
		self.assertTrue(np.isnan(result))

	def test_rsi_constant_prices(self):
		prices = np.array([50.0] * 20)
		result = IndicatorEngine.rsi(prices, period=14)
		# No losses => avg_loss = 0 => 100.0
		self.assertAlmostEqual(result, 100.0)

	def test_rsi_strictly_increasing(self):
		prices = np.linspace(100.0, 200.0, 30)
		result = IndicatorEngine.rsi(prices, period=14)
		self.assertAlmostEqual(result, 100.0)

	def test_rsi_insufficient_data(self):
		prices = np.array([10.0, 11.0, 12.0])
		result = IndicatorEngine.rsi(prices, period=14)
		self.assertTrue(np.isnan(result))

if __name__ == '__main__':
	unittest.main()
