# DeepTerminal

A terminal-based trading application built with Python's Textual library and the Upstox API.

## Features

- Authentication with Upstox API
- Instrument search across multiple exchanges (NSE, BSE, NFO, BFO, MCX, CDS)
- Live market data updates
- Order placement (Market, Limit, Stop Loss)
- Position tracking with live P&L updates
- Support for custom trading strategies

## Requirements

- Python 3.10+
- Poetry for dependency management

## Installation

1. Clone the repository:

```bash
git clone https://github.com/akasantony/deepterminal.git
cd deepterminal
```

2. Install dependencies using Poetry:

```bash
poetry install
```

3. Configure your Upstox API credentials:
   - Copy the `.env.example` file to `.env`
   - Fill in your Upstox API credentials:
     ```
     UPSTOX_API_KEY="your-api-key"
     UPSTOX_API_SECRET="your-api-secret"
     UPSTOX_REDIRECT_URI="http://localhost:8000/callback"
     ```

## Usage

1. Run the application:

```bash
poetry run trading-app
```

2. Authenticate with your Upstox account when prompted.

3. Use the app:
   - Search for instruments by symbol or name
   - Place buy/sell orders with different order types
   - Monitor your positions and P&L in real-time

## Key Bindings

- `q`: Quit the application
- `r`: Refresh data
- `Ctrl+t`: Toggle dark mode

## Adding Custom Strategies

You can implement your own trading strategies by extending the `TradingStrategy` base class:

```python
from src.trading.strategy import TradingStrategy

class MyCustomStrategy(TradingStrategy):
    def initialize(self):
        # Initialize your strategy parameters and state
        pass

    def on_tick_data(self, data):
        # Process incoming market data
        pass

    def on_position_update(self, position):
        # Handle position updates
        pass
```

## Project Structure

```
upstox-trading-app/
├── .env                      # Environment variables
├── poetry.lock              # Poetry lock file
├── pyproject.toml           # Poetry dependencies
├── README.md                # Documentation
└── src/
    ├── main.py              # Application entry point
    ├── auth/                # Authentication
    ├── api/                 # API client
    ├── ui/                  # User interface
    ├── models/              # Data models
    ├── trading/             # Trading functionality
    └── utils/               # Utilities
```

## License

MIT
