#from binance import BinanceSocketManager, AsyncClient  # ThreadedWebsocketManager
import ccxt.pro as ccxt
import asyncio
import time
from typing import List, Tuple
from decimal import Decimal
import database
import traceback
from datetime import datetime

def DecimalToString(value: Decimal) -> str:
    """Convert Decimal to string with 10 decimal places."""
    return f"{value:.10f}".rstrip('0').rstrip('.')

class Call:
    SIGNS = {"USDT": '₮', "BTC": "₿", "ETH": "Ξ", "EUR": "€", "USD": "$", "USDC": "$", "BUSD": "$"}
    def __init__(self, dbCall: database.CryptoCall, dbTakeProfits: List):
        self.__dbCall = dbCall
        self.__baseCoin, self.__quoteCoin = dbCall.pair.split("/", 1)
        self.__quoteSign = Call.SIGNS.get(self.__quoteCoin, self.__quoteCoin)
        self.__dbTakeProfits = dbTakeProfits
        self.__price = Decimal("0.0")

    @classmethod
    async def Create(cls, pair: str, exchange: str, entryPrice: Decimal, stopLoss: Decimal, takeProfits: List):
        dbCall = await database.CryptoCall.Insert(pair=pair,
                                                  exchange=exchange,
                                                  entryPrice=entryPrice,
                                                  stopLoss=stopLoss)
        dbTakeProfits = []
        amount = dbCall.investment / entryPrice
        print("Amount: ", amount)
        for takeProfit in takeProfits:
            dbTakeProfits.append(
                await database.TakeProfit.Insert(callId=dbCall.id,
                                                 targetPrice=takeProfit['targetPrice'],
                                                 amount=amount * takeProfit['size']))

        return cls(dbCall, dbTakeProfits)

    @classmethod
    async def GetById(self, callId: int):
        dbCall = await database.CryptoCall.GetById(callId)
        if dbCall is None:
            raise ValueError(f"Call with ID {callId} not found.")
        dbTakeProfits = await database.TakeProfit.GetBySelect(callId=callId)
        return Call(dbCall, dbTakeProfits)

    @classmethod
    async def GetOpenCalls(self):
        """
        Get all open calls from the database.
        """
        dbCalls = await database.CryptoCall.GetByExclude(status=database.CryptoCall.Status.CLOSED)
        openCalls = []
        for dbCall in dbCalls:
            dbTakeProfits = await database.TakeProfit.GetBySelect(callId=dbCall.id)
            openCalls.append(Call(dbCall, dbTakeProfits))
        print(f"openCalls: {openCalls}")
        return openCalls

    def __repr__(self):
        return f"<Call id={self.__dbCall.id} exchange={self.exchange} pair={self.__dbCall.pair} entryPrice={self.__dbCall.entryPrice} stopLoss={self.__dbCall.stopLoss} investment={self.__dbCall.investment} amount={self.__dbCall.amount} result={self.__dbCall.result} status={self.__dbCall.status}>"

    async def Save(self):
        await self.__dbCall.Save()
        for tp in self.__dbTakeProfits:
            await tp.Save()

    async def Cancel(self):
        """
        Cancel the call and update the database.
        """
        self.__dbCall.status = database.CryptoCall.Status.CLOSED
        self.__dbCall.closedAt = datetime.now()
        await self.Save()
        print(f"Cancelled call {self.__dbCall.id}")

    async def Close(self):
        """
        Close the call and update the database.
        """
        if self.__dbCall.status == database.CryptoCall.Status.CLOSED:
            print(f"Call {self.__dbCall.id} is already closed.")
            return

        if self.__dbCall.status == database.CryptoCall.Status.ACTIVE:
            self.__dbCall.result += self.__dbCall.amount * self.price
            self.__dbCall.amount = Decimal("0.0")
        self.__dbCall.status = database.CryptoCall.Status.CLOSED
        self.__dbCall.closedAt = datetime.now()
        await self.Save()
        await self.__SendMessage(f"Call {self.__dbCall.id} closed at {self.sign} {DecimalToString(self.price)}.")

    async def __SendMessage(self, comment: str):
        """
        Post a message to the bot's channel.
        """
        from bot import CryptoCallBot
        bot = CryptoCallBot.GetInstance()

        await bot.SendMessage(self.GetOverview(comment))

    async def __ActivateTriggered(self, klineData) -> Tuple[bool, str]:
        if klineData['high'] < self.__dbCall.entryPrice:
            # We pay less for the call than we expected
            entryPrice = klineData['high']
        else:
            entryPrice = self.__dbCall.entryPrice
        self.__dbCall.activatedAt = klineData['time']
        self.__dbCall.amount = self.__dbCall.investment / self.__dbCall.entryPrice
        self.__dbCall.entryPrice = entryPrice
        self.__dbCall.investment = self.__dbCall.amount * entryPrice
        self.__dbCall.result = -self.__dbCall.investment
        self.__dbCall.status = database.CryptoCall.Status.ACTIVE
        await self.Save()

        return True, f"Buy in at {self.sign} {DecimalToString(self.entryPrice)}."

    async def __StopLossTriggered(self, klineData) -> Tuple[bool, str]:
        self.__dbCall.status = database.CryptoCall.Status.CLOSED
        self.__dbCall.result += self.__dbCall.amount * self.__dbCall.stopLoss
        self.__dbCall.amount = Decimal("0.0")
        self.__dbCall.stopLossTriggered = klineData['time']
        self.__dbCall.closedAt = klineData['time']
        await self.Save()
        return False, f"Closed by stop loss."

    async def __TargetTriggered(self, dbTakeProfit, klineData) -> Tuple[bool, str]:
        dbTakeProfit.triggeredAt = klineData['time']
        self.__dbCall.amount -= dbTakeProfit.amount
        dbTakeProfit.result = dbTakeProfit.amount * \
            (dbTakeProfit.targetPrice - self.__dbCall.entryPrice)
        self.__dbCall.result += dbTakeProfit.amount * dbTakeProfit.targetPrice
        await self.Save()
        return True, f"Take profit {self.sign} {DecimalToString(dbTakeProfit.targetPrice)} triggered."

    async def Update(self, klineData) -> bool:
        """
        Update the call with the latest kline data.
        Returns True if the call was updated, False if the call was closed.
        """
        if self.__dbCall.status == database.CryptoCall.Status.CLOSED:
            print(f"Call {self.__dbCall.id} is already closed.")
            return False

        retVal = True
        messages = []
        self.price = klineData['close']
        if self.__dbCall.status == database.CryptoCall.Status.ACQUIRING:
            if klineData['low'] <= self.__dbCall.entryPrice:
                retVal, message = await self.__ActivateTriggered(klineData)
                messages.append(message)

        if self.__dbCall.status == database.CryptoCall.Status.ACTIVE:
            if klineData['low'] <= self.__dbCall.stopLoss:
                retVal, message = await self.__StopLossTriggered(klineData)
                messages.append(message)
            else:
                nrOfOpenTakeProfits = 0
                for tp in self.__dbTakeProfits:
                    if tp.triggeredAt is None:
                        if klineData['high'] >= tp.targetPrice:
                            retVal, message = await self.__TargetTriggered(tp, klineData)
                            messages.append(message)
                        else:
                            nrOfOpenTakeProfits += 1

                if nrOfOpenTakeProfits == 0:
                    self.__dbCall.status = database.CryptoCall.Status.CLOSED
                    self.__dbCall.closedAt = klineData['time']
                    await self.Save()
                    retVal = False
                    messages.append("Closed as all target prices have been reached.")

        if messages:
            await self.__SendMessage("\n".join(messages))
        return retVal

    def GetOverview(self, message="") -> str:
        """Get a string overview of the call."""

        firstColumnWidth = 11

        takeProfits = ""
        for tp in self.__dbTakeProfits:
            targetPercentage = ((tp.targetPrice / self.entryPrice) - 1) * 100
            value = f"{self.sign} {DecimalToString(tp.targetPrice)} ({DecimalToString(tp.amount)}) {targetPercentage:.2f}%"
            if tp.triggeredAt is not None:
                status = "Closed"
            elif self.__dbCall.status == database.CryptoCall.Status.CLOSED:
                status = "Cancelled"
            elif self.__dbCall.activatedAt is not None:
                status = "Open"
            else:
                status = ""
            takeProfits += f"\n{str(status).rjust(firstColumnWidth)} {value}"

        status = self.__dbCall.status.name
        if self.__dbCall.status == database.CryptoCall.Status.CLOSED and self.__dbCall.stopLossTriggered is not None:
            status += " (Stop Loss)"

        totalResult = self.result + self.value
        percentage = (totalResult / self.investment) * 100
        percentage = f"{percentage:.2f}%"
        comment = f"Call {self.__dbCall.id}: {'🟩' if totalResult >= 0 else '🟥'} {self.sign} {DecimalToString(totalResult)} {percentage}"
        if message:
            comment += f"\n{message}"

        stopLossPercentage = (1 - self.stopLoss / self.entryPrice) * 100

        return f"""{comment}
```
Call ID       {str(self.id)}
Pair          {str(self.pair)}
Exchange      {str(self.exchange)}
Status        {status}
Entry Price   {self.sign} {DecimalToString(self.entryPrice)}
Stop Loss     {self.sign} {DecimalToString(self.stopLoss)} {stopLossPercentage:.2f}%
Investment    {self.sign} {DecimalToString(self.investment)}
Amount Coins  {DecimalToString(self.amount)}
Current Price {self.sign} {DecimalToString(self.price)}
Current Value {self.sign} {DecimalToString(self.value)}
Result*       {self.sign} {DecimalToString(totalResult)} {percentage}

Profits{takeProfits}
```
"""

    @property
    def pair(self) -> str:
        return self.__dbCall.pair

    @property
    def quoteCoin(self) -> str:
        return self.__quoteCoin

    @property
    def sign(self) -> str:
        return self.__quoteSign

    @property
    def baseCoin(self) -> str:
        return self.__baseCoin

    @property
    def exchange(self) -> str:
        return self.__dbCall.exchange

    @property
    def entryPrice(self) -> Decimal:
        return self.__dbCall.entryPrice

    @property
    def stopLoss(self) -> Decimal:
        return self.__dbCall.stopLoss

    @property
    def investment(self) -> Decimal:
        return self.__dbCall.investment

    @property
    def amount(self) -> Decimal:
        return self.__dbCall.amount
    @amount.setter
    def amount(self, value: Decimal):
        if isinstance(value, str):
            value = Decimal(value)
        elif isinstance(value, float):
            value = Decimal.from_float(value)
        self.__dbCall.amount = value

    @property
    def takeProfits(self) -> List:
        return self.__dbTakeProfits

    @property
    def status(self) -> database.CryptoCall.Status:
        return self.__dbCall.status
    @status.setter
    def status(self, value: database.CryptoCall.Status):
        self.__dbCall.status = value

    @property
    def result(self) -> Decimal:
        return self.__dbCall.result

    @result.setter
    def result(self, value: Decimal):
        if isinstance(value, str):
            value = Decimal(value)
        elif isinstance(value, float):
            value = Decimal.from_float(value)
        self.__dbCall.result = value

    @property
    def price(self) -> Decimal:
        return self.__price
    @price.setter
    def price(self, value: Decimal):
        if isinstance(value, str):
            value = Decimal(value)
        elif isinstance(value, float):
            value = Decimal.from_float(value)
        self.__price = value

    @property
    def value(self) -> Decimal:
        return self.__price * self.amount

    @property
    def id(self) -> int:
        return self.__dbCall.id

class  CryptoExchange:
    INTERVAL = '1m'

    def __init__(self, name: str):
        if hasattr(ccxt, name):
            self.__exchange = getattr(ccxt, name)({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                },
            })
            self.__name = name

            if not hasattr(self.__exchange, 'loadMarkets'):
                raise ValueError(
                    f"Exchange {self.__exchange.name} does not support loadMarkets.")
            if not hasattr(self.__exchange, 'watchOHLCV'):
                raise ValueError(
                    f"Exchange {self.__exchange.name} does not support watchOHLCV.")
        else:
            raise ValueError(f"Exchange {name} not found.")
        self.__openCalls = {}
        self.__exchangeInfo = {'last': 0, 'symbols': None}
        self.__running = True

    async def Stop(self):
        """
        Stop the exchange and close all open calls.
        """
        self.__running = False

        openCalls = self.__openCalls.copy()
        for pairData in openCalls.values():
            if hasattr(self.__exchange, 'unWatchOHLCV'):
                await self.__exchange.unWatchOHLCV(pairData['pair'], self.INTERVAL)

        openTasks = [pairData['task'] for pairData in openCalls.values() if pairData['task'] is not None]
        await asyncio.gather(*openTasks)
        self.__openCalls = []
        print(f"Closed all calls for {self.__name}")
        if hasattr(self.__exchange, 'close'):
            await self.__exchange.close()
        print(f"Closed exchange {self.__name}")

    @property
    def name(self) -> str:
        return self.__name
    @property
    def exchange(self) -> str:
        return self.__exchange.name
    @property
    def openCalls(self) -> List[Tuple[str, str]]:
        return self.__openCalls
    @property
    def size(self) -> int:
        return len(self.__openCalls)

    async def __CheckPair(self, pair: str) -> str:
        """
        Check if the trading pair is valid. Raises an exception if not. Returns the pair if valid.
        """
        if self.__exchangeInfo is None or (time.time() - self.__exchangeInfo['last']) > 3600:
            self.__exchangeInfo['last'] = time.time()
            exchangeInfo = await self.__exchange.loadMarkets()
            self.__exchangeInfo['symbols'] = [symbol for symbol, market in exchangeInfo.items() if market['active'] and market['type'] == 'spot']
        if pair in self.__exchangeInfo['symbols']:
            return pair
        raise ValueError(f"Invalid pair: {pair}. This pair is not trading at Binance.")

    async def __HandleOhlcv(self, pairData, ohlcv) -> bool:
        # Handle the incoming OHLCV message
        # [time, open, high, low, close, volume]
        active = True
        if ohlcv and ohlcv[0] != pairData['lastOhlcv'][0]:
            pairData['lastOhlcv'] = ohlcv
            klineData = {"low": Decimal(str(ohlcv[3])),
                         "high": Decimal(str(ohlcv[2])),
                         "time": datetime.fromtimestamp(ohlcv[0] / 1000),
                         # "open": Decimal(str(ohlcv[1])),
                         "close": Decimal(str(ohlcv[4])),
                         "pair": pairData['pair']}
            callsToRemove = []
            for call in pairData['calls']:
                if not await call.Update(klineData):
                    callsToRemove.append(call)

            for call in callsToRemove:
                pairData['calls'].remove(call)
                if len(pairData['calls']) == 0:
                    active = False
        return active

    async def __WatchOhlcv(self, pair):
        pairData = self.__openCalls[pair]
        running = True

        while self.__running and running:
            try:
                msg = await self.__exchange.watchOHLCV(pair, self.INTERVAL)
                for ohlcv in msg:
                    if not await self.__HandleOhlcv(pairData, ohlcv):
                        running = False
            except Exception as e:
                print(f"Error watching OHLCV for {pair}: {e}")
                await asyncio.sleep(5)

        try:
            if self.__running and hasattr(self.__exchange, 'unWatchOHLCV'):
                await self.__exchange.unWatchOHLCV(pair, self.INTERVAL)
        except Exception as e:
            print(f"Error unwatching OHLCV for {pair}: {e}")
        del self.__openCalls[pair]
        print(f"Closed all calls for {pair}")

    async def _RegisterCall(self, call: Call):
        pair = await self.__CheckPair(call.pair)
        if pair in self.__openCalls:
            self.__openCalls[pair]['calls'].append(call)
        else:
            # load the first OHLCV to get the last price
            ohlcv = (await self.__exchange.watchOHLCV(pair, self.INTERVAL))[0]
            # only keep the close price
            lastOhlcv = [int(datetime.now().timestamp() * 1000) - 1, ohlcv[4], ohlcv[4], ohlcv[4], ohlcv[4], 0]
            self.__openCalls[pair] = {'calls': [call], 'pair': pair, 'task': None, 'lastOhlcv': lastOhlcv}
            lastOhlcv = lastOhlcv.copy()
            lastOhlcv[0] += 1
            await self.__HandleOhlcv(self.__openCalls[pair], lastOhlcv)

            self.__openCalls[pair]['task'] = asyncio.create_task(self.__WatchOhlcv(pair))
            print(f"Created task call for {pair}")

    async def AddCall(self, pair: str, entryPrice: Decimal, stopLoss: Decimal, takeProfits: List):
        await self.__CheckPair(pair)
        call = await Call.Create(pair, self.name, entryPrice, stopLoss, takeProfits)
        await self._RegisterCall(call)
        print(f"Added pair {pair} to watch.")
        return call

    def Get(self, callId: int) -> Call:
        """
        Get a call by its ID.
        """
        for pairData in self.__openCalls.values():
            for call in pairData['calls']:
                if call.id == callId:
                    return call

    def GetOpenCalls(self) -> List[Call]:
        """
        Get all open calls.
        """
        calls = []
        for pairData in self.__openCalls.values():
            calls.extend(pairData['calls'])
        return calls

class CryptoMonitor:
    def __init__(self):
        self.__client = None
        self.__bsm = None
        self.__running = False
        self.__exchanges = {}

    async def Initialize(self):
        self.__running = True
        await self.__LoadOpenCalls()

    async def Stop(self):
        self.__running = False

        for exchange in self.__exchanges.copy().values():
            await exchange.Stop()

    async def __RegisterExchange(self, exchangeName: str):
        """
        Register an exchange with the monitor.
        """
        if exchangeName in self.__exchanges:
            return self.__exchanges[exchangeName]

        exchange = CryptoExchange(exchangeName)
        self.__exchanges[exchangeName] = exchange
        return exchange


    async def AddCall(self, exchangeName: str, pair: str, entryPrice: Decimal, stopLoss: Decimal, takeProfits: List):
        exchange = await self.__RegisterExchange(exchangeName)

        try:
            call = await exchange.AddCall(pair, entryPrice, stopLoss, takeProfits)
        except ValueError:
            if exchange.size == 0:
                await exchange.Stop()
                del self.__exchanges[exchangeName]
            raise

        return call

    async def __RegisterCall(self, call: Call):
        """
        Register a call with the appropriate exchange.
        """
        exchange = await self.__RegisterExchange(call.exchange)

        await exchange._RegisterCall(call)

    async def Get(self, callId: int) -> Call:
        """
        Get a call by its ID.
        """
        # First try to find it in the open calls
        for exchange in self.__exchanges.values():
            call = exchange.Get(callId)
            if call is not None:
                return call
        return await Call.GetById(callId)

    def GetOpenCalls(self) -> List[Call]:
        """
        Get all open calls.
        """
        calls = []
        for exchange in self.__exchanges.values():
            calls.extend(exchange.GetOpenCalls())
        return calls

    async def __LoadOpenCalls(self):
        """
        Load all open calls from the database.
        """
        openCalls = await Call.GetOpenCalls()
        for call in openCalls:
            try:
                await self.__RegisterCall(call)
            except ValueError:
                call.Cancel()
        print(f"Loaded {len(openCalls)} open calls.")

    async def CloseCall(self, callId: int):
        """
        Close a call by its ID.
        """
        call = await self.Get(callId)
        if call is None:
            raise ValueError(f"Call with ID {callId} not found.")
        await call.Close()