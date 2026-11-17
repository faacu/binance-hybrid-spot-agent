# 🤖 Autonomous Crypto Trading Agent — Hybrid Technical & Sentiment Confluence

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![AI Engine](https://img.shields.io/badge/AI%20Engine-Gemini%202.5%20Flash-orange.svg?logo=google-gemini&logoColor=white)](https://ai.google.dev/)
[![Market Data](https://img.shields.io/badge/Market%20Data-CCXT%20(Binance%20Spot)-green.svg)](https://github.com/ccxt/ccxt)
[![Alerts](https://img.shields.io/badge/Notifications-Twilio%20WhatsApp-red.svg?logo=twilio&logoColor=white)](https://www.twilio.com/)
[![Tests](https://img.shields.io/badge/Tests-13%2F13%20Passing-brightgreen.svg)]()
[![Code Style](https://img.shields.io/badge/Architecture-Clean%20%2F%20SOLID-purple.svg)]()

> **Senior Software Engineering & Quantitative Portfolio Project**  
> An autonomous cryptocurrency spot paper trading engine orchestrating multi-factor algorithmic signals (Wilder's RSI, Dual-SMA trend crossovers) and real-time macro/crypto fundamental sentiment (multi-source RSS aggregation) via **Google Gemini 2.5 Flash** with strict JSON schema enforcement.

---

## 📌 Executive Summary

Modern quantitative trading requires blending high-frequency market mechanics with fast-moving fundamental news. This project implements a **Hybrid Quantitative & Sentiment Confluence Agent** built to demonstrate production-grade software engineering, clean architecture, financial risk management, and cybersecurity best practices:

- **Strict Signal Confluence**: Trades only trigger when quantitative technical indicators (momentum and trend bias) align with macro/crypto market sentiment. If signals conflict or data degrades, the engine defaults to capital preservation (`HOLD`).
- **Resilient AI Pipeline**: Integrates Google's latest `google-genai` SDK targeting `gemini-2.5-flash` with guaranteed structured JSON output (`response_mime_type="application/json"`), automated exponential retry backoff, and inter-symbol rate-limit backpressure throttling.
- **Pure NumPy Vectorization**: Technical indicators (Simple Moving Average and Wilder’s Smoothed Relative Strength Index) are computed directly with NumPy, completely eliminating brittle C-compilation dependencies (such as TA-Lib) for seamless cross-platform portability.
- **Zero-Risk In-Memory Paper Ledger**: Full-fidelity simulation via `PaperWallet` tracking fractional allocations, asset balances, and immutable transaction audit trails.
- **Event-Driven Alerting**: Non-blocking, fault-tolerant push notifications to WhatsApp via the Twilio REST API for real-time mobile trade visibility.
- **Security-First Architecture**: Follows Zero Trust and OWASP principles — zero hardcoded credentials, read-only public market data ingestion (no exchange API keys exposed), regex-based HTML sanitization on external news feeds, and fail-safe error handling.

---

## 🏛️ System Architecture

The project adheres to **SOLID design principles**, clear separation of concerns, and defensive programming:

```mermaid
flowchart TD
    subgraph Ingestion ["1. Data Ingestion Layer"]
        A1["Binance Spot (CCXT)\nPublic Anonymous Read-Only"] -->|OHLCV Candles| B1["MarketDataProvider"]
        A2["Multi-Source RSS Feeds\nYahoo, CoinDesk, Cointelegraph, Reuters"] -->|Raw XML/HTML| B2["NewsFetcher\n(HTML Sanitization & UTC Normalization)"]
    end

    subgraph Processing ["2. Quantitative Engine"]
        B1 --> C1["IndicatorEngine (NumPy)\n• SMA-10 / SMA-20\n• Wilder's Smoothed RSI-14"]
        C1 & B2 --> D1["TechnicalSnapshot\n(Immutable Dataclass Context)"]
    end

    subgraph AI ["3. AI Confluence Engine"]
        D1 --> E1["GeminiSignalAnalyzer\n(Gemini 2.5 Flash)"]
        E1 -->|Prompt with Structured JSON Schema| F1{"LLM Evaluation\n• Confluence Check\n• Confidence Threshold (≥ 60%)\n• Dynamic Allocation %"}
    end

    subgraph Execution ["4. Execution & Reporting"]
        F1 -->|BUY / SELL (Validated)| G1["PaperWallet\n• Balance Bounds Check\n• Capital Allocation Capping\n• Transaction Log"]
        F1 -->|HOLD / Low Confidence| G2["Skip & Capital Preservation"]
        G1 --> H1["ConsoleReporter (Colorama CLI)"]
        G1 -.->|Async Non-Blocking| H2["WhatsAppNotifier (Twilio Gateway)"]
    end
```

---

## 🧩 Component Breakdown & Design Patterns

| Component | Design Pattern / Role | Technical Highlights |
| :--- | :--- | :--- |
| **`SpotPaperTradingBot`** | *Orchestrator / Facade* | Coordinates cycle execution, manages symbol iterations, enforces 15-second inter-symbol rate-limiting to prevent LLM quota exhaustion (`HTTP 429`), and handles graceful shutdowns (`SIGINT`). |
| **`MarketDataProvider`** | *Adapter / Gateway* | Wraps `ccxt.binance` in public, anonymous spot mode. Ingests OHLCV candle streams without exposing private API keys to external network vectors. |
| **`IndicatorEngine`** | *Pure Functional Service* | 100% native NumPy vectorized implementation of Simple Moving Averages (SMA) and Wilder's Smoothed RSI. Zero external C-bindings required. |
| **`NewsFetcher`** | *Resilient Aggregator* | Scrapes and normalizes headlines from 4 top-tier financial RSS feeds (Yahoo Finance, CoinDesk, Cointelegraph, Reuters). Enforces regex-based HTML/script sanitization (OWASP XSS defense) and timestamp normalization. |
| **`GeminiSignalAnalyzer`** | *Strategy / AI Evaluator* | Interfaces with `google.genai` SDK using `gemini-2.5-flash`. Uses schema-enforced JSON generation (`application/json`), multi-attempt exponential retry logic, and strict prompt engineering. |
| **`PaperWallet`** | *Repository / State Ledger* | In-memory simulated accounting ledger. Implements balance validation, over-allocation capping, zero/negative input guardrails, and audit logging. |
| **`WhatsAppNotifier`** | *Observer / Messaging Gateway* | Decoupled notification service via Twilio. Wrapped in non-blocking try/except blocks so notification service hiccups never interrupt trading cycles. |
| **`ConsoleReporter`** | *Presenter / View* | High-visibility terminal dashboard built with `colorama` for live cycle telemetry, wallet status, confidence levels, and trade receipts. |

---

## 🎯 Signal & Confluence Logic

Every cycle evaluates assets through a strict multi-tier verification process:

```
                          ┌──────────────────────────┐
                          │   Technical Indicators   │
                          │ • Trend (SMA-10 vs 20)   │
                          │ • Momentum (RSI-14)      │
                          └─────────────┬────────────┘
                                        │
                                        ▼
    ┌─────────────────────┐    ┌─────────────────┐    ┌─────────────────────┐
    │  Fundamental News   ├───►│ Gemini 2.5 AI   │◄───┤ Current Asset State │
    │ • Multi-Feed RSS    │    │ Decision Engine │    │ • Price & Holdings  │
    │ • Sentiment Context │    └────────┬────────┘    └─────────────────────┘
                                        │
                                        ▼
                                ┌───────────────┐
                                │ Confluence?   │
                                └───────┬───────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
             [ YES: Aligned ]                        [ NO: Conflicting ]
                    │                                       │
                    ▼                                       ▼
         Confidence >= 60%?                              HOLD
                    │                               (Capital Preserved)
           ┌────────┴────────┐
           ▼                 ▼
        [ YES ]           [ NO ]
           │                 │
           ▼                 ▼
      EXECUTE TRADE         HOLD
   (Paper Allocation)  (Low Confidence)
```

1. **BUY Signal Condition**:
   - Technical: RSI indicates oversold ($\le 30$) OR SMA bullish crossover ($\text{SMA}_{10} > \text{SMA}_{20}$).
   - Fundamental: News sentiment is neutral-to-bullish for the specific asset.
   - Gating: Confidence score $\ge 60\%$.
2. **SELL Signal Condition**:
   - Technical: RSI indicates overbought ($\ge 70$) OR SMA bearish crossover ($\text{SMA}_{10} < \text{SMA}_{20}$).
   - Fundamental: News sentiment is neutral-to-bearish for the specific asset.
   - Gating: Confidence score $\ge 60\%$.
3. **HOLD Condition (Fail-Safe)**:
   - Triggered on conflicting signals, extreme market uncertainty, missing candle data, or downstream API timeouts.

---

## 🛡️ Cybersecurity & Defensive Engineering

- **OWASP Input Sanitization**: External RSS payloads are treated as untrusted inputs. All HTML tags, script fragments, and entity references are sanitized using regex stripping and `html.unescape` prior to prompt injection.
- **Zero Trust Secret Isolation**: Zero API keys, webhooks, or tokens are committed. Configuration is strictly injected at runtime via environment variables loaded through `python-dotenv`. An explicit [`.env.example`](file:///.env.example) is provided.
- **Least Privilege Network Footprint**: CCXT operates strictly in anonymous public read-only mode for ticker and OHLCV data. No exchange write credentials or account keys are needed for evaluation.
- **Fail-Safe / Zero Silent Failures**: Any network timeout, API throttling, or parsing error fails safe to `HOLD` with `confidence = 0.0`. Capital is never committed when system health is degraded.
- **Throttling & Backpressure**: Implements proactive sleeps between asset queries to stay well within Google GenAI rate limits (`15 RPM` on free tiers), combined with automatic retry for transient `503` service unavailability.

---

## 🧪 Automated Testing Suite

The repository includes a dedicated test suite organized into `tests/unit/` and `tests/smoke/` using Python's standard `unittest` framework (zero third-party test harness required):

- **Unit Tests (`tests/unit/`)**:
  - `test_wallet.py`: Verifies initial ledger state, BUY/SELL executions, balance deductions, over-allocation automatic capping, and protection against zero/negative inputs.
  - `test_indicators.py`: Validates calculation precision for Simple Moving Averages and Wilder's smoothed RSI, including insufficient data boundary conditions ($NaN$ checks) and edge-case price series.
- **Smoke Tests (`tests/smoke/`)**:
  - `test_smoke.py`: Tests dataclass immutability/contracts, module imports, and regex HTML sanitization across malicious or dirty input strings.

### Running the Test Suite

```bash
# Execute all unit and smoke tests
python -m unittest discover -s tests
```

Output:
```text
Ran 13 tests in 0.009s
OK
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python `3.10+`
- Google Gemini API Key ([Google AI Studio](https://aistudio.google.com/app/apikey))
- *(Optional)* Twilio Account for WhatsApp mobile alerts

### 2. Installation

```bash
# Clone repository
git clone https://github.com/<your-username>/bot-trading-futuros.git
cd bot-trading-futuros

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the template and fill in your API credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
# Required: Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Trading configuration
INITIAL_PAPER_BALANCE=1000.0
LOOP_INTERVAL_SECONDS=300

# Optional: Twilio WhatsApp Notifications (leave blank to disable)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+5491112345678
```

### 4. Verify API Connection

Run the diagnostic utility to verify connectivity with Gemini models:

```bash
python test-api.py
```

### 5. Launch the Trading Bot

```bash
python bot.py
```

---

## ⚙️ Configuration Parameters

Key operational constants are centralized in `bot.py` and can be adjusted based on trading strategy:

| Parameter | Default Value | Description |
| :--- | :--- | :--- |
| `WATCHLIST` | `['SOL/USDT']` | List of pairs tracked by the bot (e.g. `['BTC/USDT', 'SOL/USDT']`) |
| `GEMINI_MODEL` | `'gemini-2.5-flash'` | Model identifier leveraging Google GenAI SDK |
| `CANDLE_TIMEFRAME` | `'15m'` | Timeframe for OHLCV candlestick data fed to indicators |
| `CANDLE_LIMIT` | `50` | Number of historical candles fetched per asset |
| `SMA_SHORT` | `10` | Lookback period for fast moving average |
| `SMA_LONG` | `20` | Lookback period for slow moving average |
| `RSI_PERIOD` | `14` | Lookback period for Wilder's smoothed RSI |
| `MIN_CONFIDENCE` | `0.60` (60%) | Minimum AI confidence required to execute simulated orders |
| `LOOP_INTERVAL_SECONDS` | `300` (5 min) | Time delay between complete market evaluation cycles |

---

## 📂 Project Structure

```text
bot-trading-futuros/
├── .env.example              # Environment variables template (sanitized)
├── .gitignore                # Git exclusions (keys, logs, venv, caches)
├── bot.py                    # Core trading engine & orchestrator (~789 lines)
├── requirements.txt          # Production dependencies
├── test-api.py               # Standalone Gemini SDK connectivity verification
├── LICENSE                   # Open-source license (GPLv3)
├── README.md                 # Technical documentation & architectural guide
└── tests/                    # Automated testing suite
    ├── __init__.py
    ├── smoke/                # End-to-end integration & contract verification
    │   ├── __init__.py
    │   └── test_smoke.py
    └── unit/                 # Unit tests for pure logic & state mechanics
        ├── __init__.py
        ├── test_indicators.py
        └── test_wallet.py
```

---

## 🗺️ Production Roadmap & Contractor Extensibility

For production-grade real-capital deployment, the system is designed to seamlessly accept the following architectural enhancements:

- [ ] **Exchange Execution Driver**: Replace `PaperWallet` with an authenticated `CCXTOrderExecutor` using API key/secret signing to route live spot or perpetual futures orders.
- [ ] **Relational / Time-Series Persistence**: Plug in PostgreSQL / TimescaleDB with SQLAlchemy to persist order history, indicator snapshots, and PnL analytics across process restarts.
- [ ] **Asynchronous Event Loop**: Refactor market ingestion to `asyncio` and exchange WebSockets (`ccxt.pro`) for sub-second reactive execution.
- [ ] **Containerization & CI/CD**: Add multi-stage `Dockerfile`, Docker Compose stack, and GitHub Actions workflow executing the test suite on every pull request.
- [ ] **Observability**: Export Prometheus metrics (`cycle_duration_seconds`, `llm_latency_seconds`, `portfolio_value_usdt`) for Grafana visualization.

---

## 📄 License

This project is licensed under the terms of the GNU General Public License v3.0 ([LICENSE](file:///LICENSE)).
