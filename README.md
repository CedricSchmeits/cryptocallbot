# CryptoCallBot

CryptoCallBot is a Telegram bot designed to manage cryptocurrency trading calls. It allows users to create, monitor, and close trading calls while integrating with Binance for real-time price updates.

---

## Features

- **Add Trading Calls**: Create new trading calls with entry price, stop loss, and take profit targets.
- **Monitor Calls**: Automatically track the status of active calls and update users in the Telegram group.
- **Close Calls**: Manually close specific calls.
- **Real-Time Price Updates**: Integrates with Binance to fetch live price data.
- **Group and Member Validation**: Ensures only authorized users can interact with the bot.

---

## Requirements

- Python 3.10+
- MySQL database
- Binance API access
- Telegram bot token

---

## Installation

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd cryptocallbot
   ```

2. **Install Dependencies**:
   Install the required Python packages:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables**:
   Copy the example `.env` file and fill in your configuration:
   ```bash
   cp .env.example .env
   ```

   Update the `.env` file with your credentials:
   ```properties
   TELEGRAM_BOT_TOKEN=<your-bot-token>
   TELEGRAM_GROUP_CHAT_ID=<your-group-chat-id>
   TELEGRAM_BOT_NAME=CryptoCallBot

   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=<your-mysql-user>
   MYSQL_PASSWORD=<your-mysql-password>
   MYSQL_DATABASE=<your-mysql-database>
   ```

4. **Set Up the Database**:
   Ensure your MySQL database is running and the credentials in `.env` are correct. The bot will automatically create the necessary tables on startup.

---

## Usage

1. **Start the Bot**:
   Run the bot using the following command:
   ```bash
   python .
   ```

2. **Telegram Commands**:
   - `/addcall <pair> <entry> <stoploss> <take_profit> [<take_profit2> ...]`
     Create a new trading call. Example:
     ```
     /addcall BTC/USDT 50000 48000 52000 54000
     /addcall BTC/USDT 50000 10% 50@20% 50@40%
     ```
   - `/callstatus [<call_id>]`
     Check the status of a specific call or all active calls.
   - `/closecall <call_id>`
     Close a specific trading call.

---

## Project Structure

```
cryptocallbot/
├── bot/
│   ├── botsettings.py       # Handles bot settings and environment variables
│   ├── cryptocallbot.py     # Main bot logic and Telegram command handlers
├── crypto/
│   ├── cryptomonitor.py     # Manages trading calls and Binance integration
├── database/
│   ├── basemodel.py         # Base model for database interactions
│   ├── database.py          # Database connection and initialization
│   ├── takeprofit.py        # TakeProfit model for managing take profit targets
├── .env.example             # Example environment variables file
├── requirements.txt         # Python dependencies
└── README.md                # Project documentation
```

---

## Development

### Running the Bot Locally
1. Ensure your `.env` file is properly configured.
2. Start the bot:
   ```bash
   source .venv/bin/activate
   python.
   ```

---

## Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Submit a pull request with a clear description of your changes.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## Acknowledgments

- [Binance API](https://github.com/sammchardy/python-binance) for real-time cryptocurrency data.
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for Telegram bot integration.
- [aiomysql](https://github.com/aio-libs/aiomysql) for asynchronous MySQL interactions.