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
   TELEGRAM_BOT_MIN_STATUS_LEVEL=RESTRICTED
   TELEGRAM_BOT_MIN_COMMAND_LEVEL=MEMBER

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
   - `/addcall <contract_address> <exchange> <pair> <entry> <stoploss> <take_profit> [<take_profit2> ...]`
     Create a new trading call. Example:
     ```
     /addcall "" binance BTC/USDT 50000 48000 52000 54000
     /addcall 0x2170ed0880ac9a755fd29b2688956bd959f933f8 binance ETH/USDT 2000 10% 50@20% 50@40%
     ```
   - `/callstoploss <call_id> <stoploss>`
     Change a stoploss of an active call, ether by price or precentage of the current price
     ```
     /callstoploss 3 45000
     /callstoploss 3 10%
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

## Keeping Batteries Charged

Developing bots takes energy (and snacks). If you enjoyed using CryptoCallBot, send a little juice in the form of a few satoshis or some gwei.

**Bitcoin**:
`bc1qecwm6f9qnmchua267eajup2g5nmegpulxwejd7`

**Litecoin**:
`ltc1qq007rrklwgxsjzwnxdve6ff0s5lq72z5jcdgf5`

**Ethereum**:
`0xa28f1222FAA5037eb2BB8097c45b72258866D153`

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## Acknowledgments

- [Binance API](https://github.com/sammchardy/python-binance) for real-time cryptocurrency data.
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for Telegram bot integration.
- [aiomysql](https://github.com/aio-libs/aiomysql) for asynchronous MySQL interactions.