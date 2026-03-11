"""
Algorithmic trading bot for Binance Futures.
Strategy: Mean reversion scalping with 10x leverage.
AI Brain: Google Gemini Flash for OHLCV signal analysis.
Risk management: Dynamic trailing stop loss + kill switch.
"""

import os
import time
import logging
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
import ccxt
from google import genai
from google.genai import types as ai_types
from dotenv import load_dotenv
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

load_dotenv()

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s [%(levelname)s] %(message)s',
	handlers=[
		logging.StreamHandler(),
		logging.FileHandler('bot.log', encoding='utf-8'),
	],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WATCHLIST = ['BTC/USDT:USDT', 'PAXG/USDT:USDT', 'SOL/USDT:USDT']
LEVERAGE = 3
RISK_PER_TRADE = 0.01          # 1% of balance per trade (reduced for volatile assets)
KILL_SWITCH_THRESHOLD = 0.20   # Drop 20% → shut down
TRAILING_STEP_PCT = 0.015      # 1.5% default trailing step
# Per-symbol trailing step overrides for volatile assets that need more 'air'
SYMBOL_TRAILING_OVERRIDES: dict[str, float] = {
	'PIPPIN/USDT:USDT': 0.015,   # 1.5% — high volatility meme coin needs more air
}
OHLCV_TIMEFRAME = '1h'
OHLCV_LIMIT = 100              # Number of candles sent to AI
POSITION_MONITOR_INTERVAL_SECONDS = 30  # Fast loop cadence for trailing stops
SCAN_INTERVAL_SECONDS = 900    # Slow loop cadence for Gemini AI scans
GEMINI_MODEL = 'gemini-3-flash-preview'
TESTNET_MODE = os.getenv('TESTNET_MODE', 'true').lower() == 'true'


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class TrailingStop:
	"""Tracks the state of a dynamic trailing stop loss for an open position."""
	entry_price: float
	side: str                   # 'long' or 'short'
	stop_price: float
	highest_price: float        # Peak price reached since entry (long)
	lowest_price: float         # Trough price reached since entry (short)
	step_pct: float = TRAILING_STEP_PCT  # Effective step, may differ per symbol


@dataclass
class Position:
	"""Represents an active position managed by the bot."""
	symbol: str
	side: str                   # 'long' or 'short'
	entry_price: float
	size: float                 # Position size in contracts/base asset
	order_id: str
	trailing_stop: TrailingStop
	opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TradingSignal:
	"""Signal produced by the AI analysis layer."""
	symbol: str
	action: str                 # 'buy', 'sell', or 'hold'
	confidence: float           # 0.0 – 1.0
	reasoning: str


# ---------------------------------------------------------------------------
# Exchange connector
# ---------------------------------------------------------------------------
class ExchangeConnector:
	"""Wraps ccxt Binance Futures with helper methods for this bot."""

	def __init__(self, api_key: str, api_secret: str):
		self._exchange = ccxt.binanceusdm({
			'apiKey': api_key,
			'secret': api_secret,
			'options': {
				'defaultType': 'future',
				'adjustForTimeDifference': True,
			},
		})

		# Redirect all fapi endpoints to testnet without using the deprecated
		# set_sandbox_mode(), which throws NotSupported since ccxt 4.x for futures.
		if TESTNET_MODE:
			testnet_host = 'https://testnet.binancefuture.com'
			prod_host    = 'https://fapi.binance.com'
			api_urls = self._exchange.urls.get('api', {})
			for key, url in api_urls.items():
				if key.startswith('fapi') and isinstance(url, str):
					self._exchange.urls['api'][key] = url.replace(prod_host, testnet_host)
			logger.warning('\u26a0\ufe0f  TESTNET MODE ACTIVE \u2014 testnet.binancefuture.com')
		else:
			logger.warning('\ud83d\udd34 LIVE MODE ACTIVE \u2014 real funds in use!')

		# Prevent load_markets() from hitting the SAPI spot endpoint (fetch_currencies).
		# binanceusdm inherits from binance and would call sapi/v1/capital/config/getall,
		# which is a spot-only endpoint that rejects futures/testnet API keys.
		self._exchange.has['fetchCurrencies'] = False
		self._exchange.load_markets()

	def set_leverage(self, symbol: str, leverage: int) -> None:
		"""Sets the leverage for a given symbol."""
		try:
			self._exchange.set_leverage(leverage, symbol)
			logger.info('Leverage set to %dx for %s', leverage, symbol)
		except Exception as error:
			logger.warning('Could not set leverage for %s: %s', symbol, error)

	def fetch_balance(self) -> float:
		"""Returns the available USDT balance in the futures wallet."""
		balance = self._exchange.fetch_balance()
		return float(balance['USDT']['free'])

	def fetch_ohlcv(self, symbol: str) -> list[list]:
		"""Fetches the last N candles for a symbol."""
		return self._exchange.fetch_ohlcv(
			symbol, timeframe=OHLCV_TIMEFRAME, limit=OHLCV_LIMIT
		)

	def fetch_ticker(self, symbol: str) -> dict:
		"""Returns the current ticker for a symbol."""
		return self._exchange.fetch_ticker(symbol)

	def open_market_order(self, symbol: str, side: str, amount: float) -> dict:
		"""Places a market order. side must be 'buy' or 'sell'."""
		return self._exchange.create_market_order(symbol, side, amount)

	def round_amount_to_precision(self, symbol: str, amount: float) -> float:
		"""
		Rounds a raw position size to the step size required by the exchange
		for the given symbol, preventing order rejection due to excess decimals.
		"""
		rounded = self._exchange.amount_to_precision(symbol, amount)
		return float(rounded)

	def close_position(self, position: Position) -> dict:
		"""Closes an open position at market price."""
		close_side = 'sell' if position.side == 'long' else 'buy'
		logger.info(
			'Closing %s position on %s (size=%.4f)',
			position.side, position.symbol, position.size,
		)
		return self._exchange.create_market_order(
			position.symbol, close_side, position.size, params={'reduceOnly': True}
		)

	def fetch_open_positions(self) -> list[dict]:
		"""Fetches all currently open futures positions."""
		positions = self._exchange.fetch_positions()
		return [p for p in positions if float(p.get('contracts', 0)) > 0]


# ---------------------------------------------------------------------------
# AI signal generator
# ---------------------------------------------------------------------------
class GeminiSignalAnalyzer:
	"""
	Uses Google Gemini to analyse OHLCV data. 
	Updated to use the modern google-genai SDK.
	"""

	def __init__(self, api_key: str):
		self._client = genai.Client(api_key=api_key)
		self._model_id = GEMINI_MODEL

	def _build_prompt(self, symbol: str, candles: list[list]) -> str:
		"""Builds the structured prompt sent to Gemini."""
		candle_rows = '\n'.join(
			f'  [{c[0]}, O:{c[1]:.4f}, H:{c[2]:.4f}, L:{c[3]:.4f}, C:{c[4]:.4f}, V:{c[5]:.2f}]'
			for c in candles[-30:]   # Last 30 candles are enough context
		)
		return f"""
Actúa como un gestor de fondos Macro. Analiza estas velas de {OHLCV_TIMEFRAME} para {symbol} considerando el contexto de tensión geopolítica actual (EE. UU. - Irán). Busca agotamiento en las tendencias y niveles de soporte/resistencia fuertes. No operes si el mercado está esperando una noticia de alto impacto (volatilidad plana). Prioriza entradas donde el riesgo/beneficio sea de al menos 1:3.

Candles (timestamp, open, high, low, close, volume):
{candle_rows}

Rules:
- A BUY signal means price is at a strong support level or trend exhaustion, with a favorable risk/reward.
- A SELL signal means price is at a strong resistance level or trend exhaustion, with a favorable risk/reward.
- A HOLD signal means no clear opportunity, or market is waiting for high impact news (flat volatility).
- Priority is capital preservation over trade frequency.

Respond ONLY with a valid JSON object, no markdown, no commentary:
{{
  "action": "buy" | "sell" | "hold",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence>"
}}
"""

	def analyse(self, symbol: str, candles: list[list]) -> TradingSignal:
		"""Calls Gemini and parses the trading signal."""
		prompt = self._build_prompt(symbol, candles)
		try:
			response = self._client.models.generate_content(
				model=self._model_id,
				contents=prompt,
				config=ai_types.GenerateContentConfig(
					response_mime_type='application/json'
				)
			)
			
			raw_text = response.text.strip()
			parsed = json.loads(raw_text)
			
			return TradingSignal(
				symbol=symbol,
				action=parsed.get('action', 'hold').lower(),
				confidence=float(parsed.get('confidence', 0.0)),
				reasoning=parsed.get('reasoning', ''),
			)
		except Exception as error:
			logger.error('Gemini API error for %s: %s', symbol, error)
			return TradingSignal(symbol=symbol, action='hold', confidence=0.0, reasoning='API error')


# ---------------------------------------------------------------------------
# Risk manager
# ---------------------------------------------------------------------------
class RiskManager:
	"""
	Enforces position sizing, trailing stop updates and the kill switch.
	All risk decisions pass through here.
	"""

	def __init__(self, initial_balance: float):
		self._initial_balance = initial_balance
		self._killed = False

	@property
	def is_killed(self) -> bool:
		return self._killed

	def check_kill_switch(self, current_balance: float) -> bool:
		"""
		Returns True and sets the killed flag if the balance has dropped
		more than KILL_SWITCH_THRESHOLD below the initial balance.
		"""
		drawdown = (self._initial_balance - current_balance) / self._initial_balance
		if drawdown >= KILL_SWITCH_THRESHOLD:
			logger.critical(
				'KILL SWITCH ACTIVATED — drawdown %.1f%% (balance: $%.2f / initial: $%.2f)',
				drawdown * 100, current_balance, self._initial_balance,
			)
			self._killed = True
		return self._killed

	def calculate_position_size(self, balance: float, entry_price: float, stop_price: float) -> float:
		"""
		Calculates the position size (in base asset units) using fixed
		fractional risk: risk_amount / distance_to_stop.
		"""
		risk_amount = balance * RISK_PER_TRADE
		distance = abs(entry_price - stop_price)
		if distance == 0:
			return 0.0
		raw_size = risk_amount / distance
		# Apply leverage ceiling: never risk more than leverage * balance
		max_notional = balance * LEVERAGE
		max_size = max_notional / entry_price
		return min(raw_size, max_size)

	def initialise_trailing_stop(self, symbol: str, side: str, entry_price: float) -> TrailingStop:
		"""
		Creates the initial trailing stop. Volatile symbols defined in
		SYMBOL_TRAILING_OVERRIDES get a wider step to survive price noise.
		"""
		step_pct = SYMBOL_TRAILING_OVERRIDES.get(symbol, TRAILING_STEP_PCT)
		stop_price = entry_price * (1 - step_pct) if side == 'long' else entry_price * (1 + step_pct)
		return TrailingStop(
			entry_price=entry_price,
			side=side,
			stop_price=stop_price,
			highest_price=entry_price,
			lowest_price=entry_price,
			step_pct=step_pct,
		)

	def update_trailing_stop(self, trailing: TrailingStop, current_price: float) -> TrailingStop:
		"""
		Advances the trailing stop when price moves in favour.
		Uses the step_pct stored in the TrailingStop (may be a per-symbol override).
		Never moves the stop against the position.
		"""
		if trailing.side == 'long':
			if current_price > trailing.highest_price:
				trailing.highest_price = current_price
				new_stop = current_price * (1 - trailing.step_pct)
				trailing.stop_price = max(trailing.stop_price, new_stop)
		else:  # short
			if current_price < trailing.lowest_price:
				trailing.lowest_price = current_price
				new_stop = current_price * (1 + trailing.step_pct)
				trailing.stop_price = min(trailing.stop_price, new_stop)
		return trailing

	def is_stop_triggered(self, trailing: TrailingStop, current_price: float) -> bool:
		"""Returns True if the current price has hit the trailing stop level."""
		if trailing.side == 'long':
			return current_price <= trailing.stop_price
		return current_price >= trailing.stop_price


# ---------------------------------------------------------------------------
# Position manager
# ---------------------------------------------------------------------------
class PositionManager:
	"""Maintains the in-memory registry of open positions."""

	def __init__(self):
		self._positions: dict[str, Position] = {}

	def has_position(self, symbol: str) -> bool:
		return symbol in self._positions

	def get_position(self, symbol: str) -> Optional[Position]:
		return self._positions.get(symbol)

	def add_position(self, position: Position) -> None:
		self._positions[symbol := position.symbol] = position
		logger.info('Position opened: %s %s @ %.4f', position.side, symbol, position.entry_price)

	def remove_position(self, symbol: str) -> None:
		self._positions.pop(symbol, None)
		logger.info('Position closed for %s', symbol)

	def all_symbols(self) -> list[str]:
		return list(self._positions.keys())


# ---------------------------------------------------------------------------
# Console reporter (colored terminal output, separate from file logging)
# ---------------------------------------------------------------------------
class ConsoleReporter:
	"""Prints colored, human-friendly status lines to the terminal."""

	def scan_start(self) -> None:
		"""Prints the [SCANNING] prefix at the beginning of each cycle."""
		print(f'\n{Fore.CYAN}[SCANNING]{Style.RESET_ALL}', end=' ', flush=True)

	def scan_symbol(self, symbol: str) -> None:
		"""Prints each symbol name inline as the scan progresses."""
		short_name = symbol.split('/')[0]
		print(f'{short_name}...', end=' ', flush=True)

	def scan_done(self) -> None:
		"""Closes the scan line with a newline."""
		print()

	def print_balance(self, balance: float) -> None:
		print(f'  {Fore.YELLOW}[BALANCE]{Style.RESET_ALL} ${balance:.2f} USDT')

	def print_signal(self, action: str, symbol: str, confidence: float, size: float, reasoning: str) -> None:
		"""Prints a BUY (green) or SELL (red) trade signal."""
		color = Fore.GREEN if action == 'buy' else Fore.RED
		print(
			f'  {color}[{action.upper()}]{Style.RESET_ALL} '
			f'{symbol} | confidence={confidence:.0%} | size={size:.4f}'
			f'\n    {Fore.WHITE}reason:{Style.RESET_ALL} {reasoning}'
		)

	def print_hold(self, symbol: str, confidence: float, reasoning: str) -> None:
		print(
			f'  {Fore.WHITE}[HOLD]{Style.RESET_ALL} '
			f'{symbol} | confidence={confidence:.0%} | {reasoning}'
		)

	def print_trailing_update(self, symbol: str, side: str, price: float, stop: float) -> None:
		print(
			f'  {Fore.MAGENTA}[TRAILING]{Style.RESET_ALL} '
			f'{symbol} ({side}) | price={price:.4f} → stop={stop:.4f}'
		)

	def print_stop_triggered(self, symbol: str, price: float, stop: float) -> None:
		print(
			f'  {Fore.MAGENTA}[STOP HIT]{Style.RESET_ALL} '
			f'{symbol} | price={price:.4f} hit stop={stop:.4f} — closing position'
		)

	def print_kill_switch(self, balance: float, initial: float, drawdown: float) -> None:
		print(
			f'\n{Fore.RED}{'=' * 60}{Style.RESET_ALL}'
			f'\n{Fore.RED}[🚨 KILL SWITCH ACTIVATED]{Style.RESET_ALL}'
			f' drawdown={drawdown:.1%} | balance=${balance:.2f} / initial=${initial:.2f}'
			f'\n{Fore.RED}{'=' * 60}{Style.RESET_ALL}'
		)


# ---------------------------------------------------------------------------
# Core bot
# ---------------------------------------------------------------------------
class TradingBot:
	"""
	Orchestrates the full trading loop:
	  1. Fetch balance → kill switch check
	  2. For each symbol in the watchlist:
	     a. Update / close existing positions via trailing stop
	     b. If no position: fetch OHLCV → AI signal → open position
	"""

	def __init__(self):
		self._exchange = ExchangeConnector(
			api_key=os.getenv('BINANCE_API_KEY', ''),
			api_secret=os.getenv('BINANCE_API_SECRET', ''),
		)
		self._ai = GeminiSignalAnalyzer(api_key=os.getenv('GEMINI_API_KEY', ''))
		self._positions = PositionManager()
		self._reporter = ConsoleReporter()

		# Snapshot balance at startup for kill switch reference
		initial_balance = self._exchange.fetch_balance()
		self._risk = RiskManager(initial_balance=initial_balance)
		logger.info('Bot started — initial balance: $%.2f USDT', initial_balance)

		# Set leverage for all symbols at startup
		for symbol in WATCHLIST:
			self._exchange.set_leverage(symbol, LEVERAGE)
			
		self._last_scan_time = 0.0  # Force scan on first tick

	# ------------------------------------------------------------------
	# Trade lifecycle helpers
	# ------------------------------------------------------------------

	def _open_position(self, signal: TradingSignal, balance: float) -> None:
		"""Opens a new leveraged position based on an AI signal."""
		ticker = self._exchange.fetch_ticker(signal.symbol)
		entry_price = float(ticker['last'])

		trailing = self._risk.initialise_trailing_stop(signal.symbol, signal.action, entry_price)
		raw_size = self._risk.calculate_position_size(balance, entry_price, trailing.stop_price)

		# Round to exchange precision BEFORE validation — a raw float like
		# 0.00312847 BTC would be rejected by Binance (step size is 0.001 BTC)
		size = self._exchange.round_amount_to_precision(signal.symbol, raw_size)

		if size <= 0:
			logger.warning('Calculated size is 0 for %s after precision rounding, skipping.', signal.symbol)
			return

		ccxt_side = 'buy' if signal.action == 'buy' else 'sell'
		order = self._exchange.open_market_order(signal.symbol, ccxt_side, size)

		position = Position(
			symbol=signal.symbol,
			side='long' if signal.action == 'buy' else 'short',
			entry_price=entry_price,
			size=size,
			order_id=order['id'],
			trailing_stop=trailing,
		)
		self._positions.add_position(position)
		logger.info(
			'Signal: %s %s | confidence=%.0f%% | size=%.4f | reason: %s',
			signal.action.upper(), signal.symbol,
			signal.confidence * 100, size, signal.reasoning,
		)
		self._reporter.print_signal(signal.action, signal.symbol, signal.confidence, size, signal.reasoning)

	def _manage_existing_position(self, position: Position) -> None:
		"""Updates trailing stop and closes the position if stop is hit."""
		ticker = self._exchange.fetch_ticker(position.symbol)
		current_price = float(ticker['last'])

		position.trailing_stop = self._risk.update_trailing_stop(
			position.trailing_stop, current_price
		)

		if self._risk.is_stop_triggered(position.trailing_stop, current_price):
			logger.info(
				'Trailing stop hit for %s — price=%.4f stop=%.4f',
				position.symbol, current_price, position.trailing_stop.stop_price,
			)
			self._reporter.print_stop_triggered(position.symbol, current_price, position.trailing_stop.stop_price)
			self._exchange.close_position(position)
			self._positions.remove_position(position.symbol)
		else:
			self._reporter.print_trailing_update(
				position.symbol, position.side, current_price, position.trailing_stop.stop_price
			)
			logger.debug(
				'%s %s | price=%.4f | trailing_stop=%.4f',
				position.side, position.symbol,
				current_price, position.trailing_stop.stop_price,
			)

	def _scan_for_signals(self, symbol: str, balance: float) -> None:
		"""Asks AI for a signal if no open position exists."""
		if self._positions.has_position(symbol):
			return

		# No open position — ask AI for a signal
		candles = self._exchange.fetch_ohlcv(symbol)
		signal = self._ai.analyse(symbol, candles)
		logger.info(
			'AI signal for %-20s → %-4s (confidence=%.0f%%)',
			symbol, signal.action.upper(), signal.confidence * 100,
		)

		# Only trade on high-confidence signals
		if signal.action in ('buy', 'sell') and signal.confidence >= 0.70:
			self._open_position(signal, balance)
		else:
			self._reporter.print_hold(symbol, signal.confidence, signal.reasoning)

	# ------------------------------------------------------------------
	# Main loop
	# ------------------------------------------------------------------

	def run(self) -> None:
		"""Starts the main trading loop. Runs until kill switch is activated."""
		logger.info('=== Trading loop started ===')
		while True:
			try:
				balance = self._exchange.fetch_balance()
				
				if self._risk.check_kill_switch(balance):
					drawdown = (self._risk._initial_balance - balance) / self._risk._initial_balance
					self._reporter.print_kill_switch(balance, self._risk._initial_balance, drawdown)
					# Close all open positions before halting
					for symbol in self._positions.all_symbols():
						position = self._positions.get_position(symbol)
						if position:
							self._exchange.close_position(position)
					logger.critical('All positions closed. Bot is halting.')
					break

				current_time = time.time()
				is_scan_time = (current_time - self._last_scan_time) >= SCAN_INTERVAL_SECONDS

				# 1. Fast Loop: Monitor open positions and trailing stops
				open_symbols = self._positions.all_symbols()
				if open_symbols:
					for symbol in open_symbols:
						position = self._positions.get_position(symbol)
						if position:
							self._manage_existing_position(position)

				# 2. Slow Loop: Scan for new entries via Gemini AI
				if is_scan_time:
					logger.info('Current balance: $%.2f USDT', balance)
					self._reporter.print_balance(balance)
					self._reporter.scan_start()
					for symbol in WATCHLIST:
						# Only scan symbols that don't have an active position
						if not self._positions.has_position(symbol):
							self._reporter.scan_symbol(symbol)
							self._scan_for_signals(symbol, balance)
					self._reporter.scan_done()
					self._last_scan_time = time.time()

			except ccxt.NetworkError as error:
				logger.error('Network error: %s — retrying in %ds', error, POSITION_MONITOR_INTERVAL_SECONDS)
			except ccxt.ExchangeError as error:
				logger.error('Exchange error: %s', error)
			except Exception as error:
				logger.exception('Unexpected error: %s', error)

			time.sleep(POSITION_MONITOR_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
	bot = TradingBot()
	bot.run()
