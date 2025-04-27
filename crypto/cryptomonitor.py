from binance import BinanceSocketManager, AsyncClient  # ThreadedWebsocketManager
import asyncio
import time
from typing import List
from decimal import Decimal
import database
import traceback
from datetime import datetime

def DecimalToString(value: Decimal) -> str:
    """Convert Decimal to string with 10 decimal places."""
    return f"{value:.10f}".rstrip('0').rstrip('.')

class Call:
    def __init__(self, dbCall: database.CryptoCall, dbTakeProfits: List):
        self.__dbCall = dbCall
        self.__dbTakeProfits = dbTakeProfits
        self.__price = Decimal("0.0")

    @classmethod
    async def Create(cls, pair: str, entryPrice: Decimal, stopLoss: Decimal, takeProfits: List):
        dbCall = await database.CryptoCall.Insert(pair=pair,
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
        return f"<Call id={self.__dbCall.id} pair={self.__dbCall.pair} entryPrice={self.__dbCall.entryPrice} stopLoss={self.__dbCall.stopLoss} investment={self.__dbCall.investment} amount={self.__dbCall.amount} result={self.__dbCall.result} status={self.__dbCall.status}>"

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
        await self.__SendMessage(f"Call {self.__dbCall.id} closed at ₮ {DecimalToString(self.price)}.")

    async def __SendMessage(self, comment: str):
        """
        Post a message to the bot's channel.
        """
        from bot import CryptoCallBot
        bot = CryptoCallBot.GetInstance()

        await bot.SendMessage(f"{comment}\n\n{self.GetOverview()}")

    async def __ActivateTriggered(self, klineData) -> bool:
        self.__dbCall.activatedAt = klineData['time']
        self.__dbCall.amount = self.__dbCall.investment / self.__dbCall.entryPrice
        self.__dbCall.result = -self.__dbCall.investment
        self.__dbCall.status = database.CryptoCall.Status.ACTIVE
        await self.Save()

        await self.__SendMessage(f"Call {self.__dbCall.id} buy in at ₮ {DecimalToString(self.entryPrice)}.")
        return True

    async def __StopLossTriggered(self, klineData) -> bool:
        self.__dbCall.status = database.CryptoCall.Status.CLOSED
        self.__dbCall.result += self.__dbCall.amount * self.__dbCall.stopLoss
        self.__dbCall.amount = Decimal("0.0")
        self.__dbCall.stopLossTriggered = klineData['time']
        self.__dbCall.closedAt = klineData['time']
        await self.Save()
        await self.__SendMessage(f"Call {self.__dbCall.id} closed by stop loss.")
        return False

    async def __TargetTriggered(self, dbTakeProfit, klineData) -> bool:
        dbTakeProfit.triggeredAt = klineData['time']
        self.__dbCall.amount -= dbTakeProfit.amount
        dbTakeProfit.result = dbTakeProfit.amount * \
            (dbTakeProfit.targetPrice - self.__dbCall.entryPrice)
        self.__dbCall.result += dbTakeProfit.amount * dbTakeProfit.targetPrice
        await self.Save()
        await self.__SendMessage(f"Take profit ₮ {DecimalToString(dbTakeProfit.targetPrice)} triggered.")
        return True

    async def Update(self, klineData) -> bool:
        """
        Update the call with the latest kline data.
        Returns True if the call was updated, False if the call was closed.
        """
        if self.__dbCall.status == database.CryptoCall.Status.CLOSED:
            print(f"Call {self.__dbCall.id} is already closed.")
            return False

        self.price = klineData['close']
        if self.__dbCall.status == database.CryptoCall.Status.ACQUIRING:
            if klineData['low'] <= self.__dbCall.entryPrice:
                await self.__ActivateTriggered(klineData)

        if self.__dbCall.status == database.CryptoCall.Status.ACTIVE:
            if klineData['low'] <= self.__dbCall.stopLoss:
                return await self.__StopLossTriggered(klineData)
            else:
                nrOfOpenTakeProfits = 0
                for tp in self.__dbTakeProfits:
                    if tp.triggeredAt is None:
                        if  klineData['high'] >= tp.targetPrice:
                            await self.__TargetTriggered(tp, klineData)
                        else:
                            nrOfOpenTakeProfits += 1

                if nrOfOpenTakeProfits == 0:
                    self.__dbCall.status = database.CryptoCall.Status.CLOSED
                    self.__dbCall.closedAt = klineData['time']
                    await self.Save()
                    await self.__SendMessage(f"Call {self.__dbCall.id} closed as all target prices have been reached.")
                    return False
        return True

    def GetOverview(self) -> str:
        """Get a string overview of the call."""

        firstColumnWidth = 11
        secondColumnWidth = 26
        separator = "|"
        divider = f"{separator}{'-' * (firstColumnWidth + 2)}{separator}{'-' * (secondColumnWidth + 2)}{separator}"
        takeProfits = ""
        for tp in self.__dbTakeProfits:
            value = f"₮ {DecimalToString(tp.targetPrice)} ({DecimalToString(tp.amount)})"
            if tp.triggeredAt is not None:
                status = "Closed"
            elif self.__dbCall.status == database.CryptoCall.Status.CLOSED:
                status = "Cancelled"
            elif self.__dbCall.activatedAt is not None:
                status = "Open"
            else:
                status = ""
            takeProfits += f"\n| {str(status).rjust(firstColumnWidth)} | {value.ljust(secondColumnWidth)} |"

        status = self.__dbCall.status.name
        if self.__dbCall.status == database.CryptoCall.Status.CLOSED and self.__dbCall.stopLossTriggered is not None:
            status += " (Stop Loss)"

        totalResult = self.result + self.value
        comment = f"Call {self.__dbCall.id}: {'🟩' if totalResult >= 0 else '🟥'} ₮ {DecimalToString(totalResult)}"
        return f"""{comment}
```
{divider}
| Call ID     | {str(self.id).ljust(secondColumnWidth)} |
| Pair        | {str(self.pair).ljust(secondColumnWidth)} |
| Status      | {status.ljust(secondColumnWidth)} |
| Entry Price | ₮ {DecimalToString(self.entryPrice).ljust(secondColumnWidth - 2)} |
| Stop Loss   | ₮ {DecimalToString(self.stopLoss).ljust(secondColumnWidth - 2)} |
| Investment  | ₮ {DecimalToString(self.investment).ljust(secondColumnWidth - 2)} |
| Remaining   | {DecimalToString(self.amount).ljust(secondColumnWidth)} |
| Price*      | ₮ {DecimalToString(self.price).ljust(secondColumnWidth - 2)} |
| Value*      | ₮ {DecimalToString(self.value).ljust(secondColumnWidth - 2)} |
| Result*     | ₮ {DecimalToString(totalResult).ljust(secondColumnWidth - 2)} |
{divider}
| Profits     | {str("").ljust(secondColumnWidth)} |{takeProfits}
{divider}
```
"""

    @property
    def pair(self) -> str:
        return self.__dbCall.pair

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

class CryptoMonitor:
    def __init__(self):
        self.__client = None
        self.__bsm = None
        self.__running = False
        self.__task = None
        self.__openCalls = {}
        self.__exchangeInfo = {'last': 0, 'symbols': None}

    async def Initialize(self):
        self.__client = await AsyncClient.create()
        self.__bsm = BinanceSocketManager(self.__client)
        self.__running = True
        await self.__LoadOpenCalls()

    async def Stop(self):
        self.__running = False
        for pairData in self.__openCalls.copy().values():
            if pairData['task'] is not None:
                pairData['task'].cancel()

        if self.__bsm is not None:
            self.__bsm = None
        if self.__client is not None:
            await self.__client.close_connection()
            self.__client = None

    async def __HandleKline(self, pairData, msg) -> bool:
        # {'t': 1745691180000,
        #  'T': 1745691239999,
        #  's': 'BTCUSDT',
        #  'i': '1m',
        #  'f': 4853411419,
        #  'L': 4853412364,
        #  'o': '94304.35000000',
        #  'c': '94300.20000000',
        #  'h': '94304.35000000',
        #  'l': '94300.19000000',
        #  'v': '1.27534000',
        #  'n': 946,
        #  'x': True,
        #  'q': '120266.16467580',
        #  'V': '0.18833000',
        #  'Q': '17759.71510360',
        #  'B': '0'}
        active = True
        if msg and msg['e'] == 'kline' and msg['k']['x'] == True:
            k = msg['k']
            klineData = { "low": Decimal(k['l']),
                          "high": Decimal(k['h']),
                          "time": datetime.fromtimestamp((k['T'] + 1) / 1000),
                          #"open": Decimal(k['o']),
                          "close": Decimal(k['c']),
                          "pair": k['s']}
            callsToRemove = []
            for call in pairData['calls']:
                if not await call.Update(klineData):
                    callsToRemove.append(call)

            for call in callsToRemove:
                pairData['calls'].remove(call)
                if len(pairData['calls']) == 0:
                    active = False
        return active

    async def __ReceiveKlines(self, pair):
        pairData = self.__openCalls[pair]
        running = True
        async with pairData['socket'] as stream:
            while self.__running and running:
                try:
                    msg = await stream.recv()
                    if not await self.__HandleKline(pairData, msg):
                        running = False
                except Exception:
                    traceback.print_exc()

        del self.__openCalls[pair]
        print(f"Closed all calls for {pair}")

    async def __RegisterCall(self, call: Call):
        binancePair = await self.__CheckPair(call.pair)
        if binancePair in self.__openCalls:
            self.__openCalls[binancePair]['calls'].append(call)
        else:
            socket = self.__bsm.kline_socket(symbol=binancePair, interval=AsyncClient.KLINE_INTERVAL_1MINUTE)
            await socket.connect()
            self.__openCalls[binancePair] = {'calls': [call], 'pair': binancePair, 'socket': socket, 'task': None}
            self.__openCalls[binancePair]['task'] = asyncio.create_task(self.__ReceiveKlines(binancePair))
            print(f"Registered call for {binancePair}")


    async def AddCall(self, pair: str, entryPrice: Decimal, stopLoss: Decimal, takeProfits: List):
        await self.__CheckPair(pair)
        call = await Call.Create(pair, entryPrice, stopLoss, takeProfits)
        await self.__RegisterCall(call)

        return call

    async def __CheckPair(self, pair: str) -> str:
        """
        Check if the trading pair is valid. Raises an exception if not. Returns the pair if valid.
        """
        binancePair = pair.upper().replace("/", "")
        if not binancePair.endswith("USDT"):
            raise ValueError(
                f"Invalid pair: {pair}. Only USDT pairs are supported.")

        if self.__exchangeInfo is None or (time.time() - self.__exchangeInfo['last']) > 3600:
            self.__exchangeInfo['last'] = time.time()
            exchangeInfo = await self.__client.get_exchange_info()
            self.__exchangeInfo['symbols'] = [s['symbol']
                                              for s in exchangeInfo['symbols'] if s['status'] == 'TRADING']
        if binancePair in self.__exchangeInfo['symbols']:
            return binancePair
        raise ValueError(
            f"Invalid pair: {pair}. This pair is not trading at Binance.")

    async def Get(self, callId: int) -> Call:
        """
        Get a call by its ID.
        """
        # First try to find it in the open calls
        for pairData in self.__openCalls.values():
            for call in pairData['calls']:
                if call.id == callId:
                    return call
        return await Call.GetById(callId)

    async def GetOpenCalls(self) -> List[Call]:
        """
        Get all open calls.
        """
        calls = []
        for pairData in self.__openCalls.values():
            calls.extend(pairData['calls'])
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