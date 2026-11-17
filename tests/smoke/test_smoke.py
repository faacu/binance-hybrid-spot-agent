import unittest
from datetime import datetime, timezone
import bot

class TestSmoke(unittest.TestCase):
	def test_dataclass_initialization(self):
		candle = bot.Candle(
			timestamp=datetime.now(timezone.utc),
			open=100.0,
			high=105.0,
			low=99.0,
			close=104.0,
			volume=1200.0
		)
		self.assertEqual(candle.close, 104.0)

		snapshot = bot.TechnicalSnapshot(
			symbol='SOL/USDT',
			last_price=104.0,
			candles=[candle],
			sma_short=102.0,
			sma_long=100.0,
			rsi=55.0,
			news_summary='Market is neutral.'
		)
		self.assertEqual(snapshot.symbol, 'SOL/USDT')

		signal = bot.TradeSignal(
			symbol='SOL/USDT',
			action='BUY',
			confidence=0.85,
			allocation_pct=0.20,
			reasoning='Strong confluence.'
		)
		self.assertEqual(signal.action, 'BUY')

	def test_news_fetcher_html_cleaning(self):
		dirty_html = '<p>Bitcoin reaches <b>new ATH</b> &amp; climbs further.</p>'
		cleaned = bot.NewsFetcher._clean_html(dirty_html)
		self.assertEqual(cleaned, 'Bitcoin reaches new ATH & climbs further.')

if __name__ == '__main__':
	unittest.main()
