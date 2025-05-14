#!/usr/bin/env python
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from telegram.constants import ParseMode
from telegram.error import RetryAfter
from dotenv import load_dotenv
from decimal import Decimal
import traceback
from version import __version__

from .botsettings import BotSettings
import database
from crypto import CryptoMonitor, Call

load_dotenv()


class CryptoCallBot:
    __singelton = None
    __methodDocumentation = {
        "call": """/addcall <contract_address> <exchange> <pair> <entry> <stoploss> <take_profit> [<take_profit2> ...]
  Create a new crypto call. The bot will send a message to the group with the call details. As buy in amount ₮ 100 is used.
   • <contractAddress> - The contract address of the token (e.g., 0x1234567890abcdef1234567890abcdef12345678 or "" when base token doesn't have a contract address)
   • <exchange> - The exchange to use (e.g., binance)
   • <pair> - The crypto pair to trade (e.g., BTC/USDT)
   • <entry> - The entry price for the trade
   • <stoploss> - The stop loss price for the trade can be a percentage or a entry price
   • <take_profit> - The take profit price for the trade can be a percentage or a entry price (add a % behind the value), when using multiple take profits, equal batches are used of the amount of bought coins. Also with a prefixed with a <precentage>@ different batch sizes can be setup, e.g 20@20% 20@50% 60@100%""",
        "status": """/callstatus [<call_id>]
  Show the status of a specific call or all calls that are in progress.
   • <call_id> - The ID of the call to check. If not provided, show all calls.""",
        "stoploss": """/callstoploss <call_id> <stoploss>
  Set the stop loss for a specific call.
   • <call_id> - The ID of the call to set the stop loss for.
   • <stoploss> - The new stop loss price for the call can be a percentage of the current price or a fixed price""",
   "close": """/closecall <call_id>
  Close a specific call."""}

    def __init__(self):
        self.__application = Application.builder()\
           .token(BotSettings.GetBotToken())\
           .post_init(self.__PostInit)\
           .post_shutdown(self.__PostShutdown)\
           .build()

        self.__monitor = CryptoMonitor()

        self.__application.add_handler(CommandHandler("start", self.Start))
        self.__application.add_handler(CommandHandler("addcall", self.OnAddCall))
        self.__application.add_handler(CommandHandler("callstatus", self.OnCallStatus))
        self.__application.add_handler(CommandHandler("closecall", self.OnCloseCall))
        self.__application.add_handler(CommandHandler("callstoploss", self.OnCallStopLoss))

    def GetApplication(self) -> Application:
        return self.__application

    async def CheckCaller(self, update: Update, context: CallbackContext, isCommand: bool = True) -> bool:
        if not await BotSettings.IsFromMember(update, context, isCommand):
            await update.message.reply_text("You don't have enough rights to use this command!")
            return False
        return True

    async def Start(self, update: Update, context: CallbackContext) -> None:
        if not await self.CheckCaller(update, context, False):
            return

        docText = '\n\n'.join(self.__methodDocumentation.values())
        await update.message.reply_text(BotSettings.EscapeMarkdownV2(f"Welcome to the **{BotSettings.GetBotName()}**!\n{docText}"),
                                        parse_mode=ParseMode.MARKDOWN_V2)

    async def UpdateCall(self, call: Call, reason: str) -> None:
        try:
            await self.__application.bot.send_message(chat_id=BotSettings.GetGroupChatId(),
                                                     text=BotSettings.EscapeMarkdownV2(
                                                         f"{reason}\n\n{call.GetOverview()}"),
                                                     parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            print(f"Error sending message: {e}")

    async def OnAddCall(self, update: Update, context: CallbackContext) -> None:
        if not await self.CheckCaller(update, context, True):
            return

        if len(context.args) < 6:
            await update.message.reply_text(BotSettings.EscapeMarkdownV2(f"Usage:\n{self.__methodDocumentation['call']}"), parse_mode=ParseMode.MARKDOWN_V2)
            return

        try:
            contractAddress = context.args[0]
            exchange = context.args[1]
            pair = context.args[2]
            entryPrice = Decimal(context.args[3])
            stopLoss = context.args[4]
            if stopLoss.endswith('%'):
                stopLoss = entryPrice * (1 - Decimal(stopLoss[:-1]) / 100)
            else:
                stopLoss = Decimal(stopLoss)

            nrOfTakeProfits = len(context.args) - 5
            takeProfits = []
            for i in range(nrOfTakeProfits):
                targetPrice = context.args[i + 5]
                if "@" in targetPrice:
                    batchSize, targetPrice = targetPrice.split("@")
                    batchSize = Decimal(batchSize) / 100
                else:
                    batchSize = Decimal(1) / nrOfTakeProfits

                if targetPrice.endswith('%'):
                    targetPrice = entryPrice * \
                        (1 + Decimal(targetPrice[:-1]) / 100)
                else:
                    targetPrice = Decimal(targetPrice)

                takeProfits.append(
                    {"targetPrice": targetPrice, "size": batchSize})

            call = await self.__monitor.AddCall(contractAddress, exchange, pair, entryPrice, stopLoss, takeProfits)
            await update.message.reply_text(BotSettings.EscapeMarkdownV2(call.GetOverview()),
                                            parse_mode=ParseMode.MARKDOWN_V2)
        except ValueError as e:
            await update.message.reply_text(f"Invalid arguments. error: {e}")
        except RetryAfter as e:
            # Most likely the bot has alread sent a message to the group chat and is rate limited
            # by Telegram. In this case we can ditch the message.
            print(f"Rate limit exceeded. Retry after {e.retry_after} seconds.")
        except Exception:
            traceback.print_exc()
            await update.message.reply_text("An error occurred while creating the call.")


    async def OnCallStopLoss(self, update: Update, context: CallbackContext) -> None:
        if not await self.CheckCaller(update, context, True):
            return

        if len(context.args) != 2:
            await update.message.reply_text(BotSettings.EscapeMarkdownV2(f"Usage:\n{self.__methodDocumentation['stoploss']}"), parse_mode=ParseMode.MARKDOWN_V2)
            return
        try:
            callId = int(context.args[0])
            call = await self.__monitor.Get(callId)
            if not call:
                await update.message.reply_text(f"Call ID {callId} not found.")
                return
            if call.status == database.CryptoCall.Status.CLOSED:
                await update.message.reply_text(f"Call ID {callId} is not active.")
                return

            stopLoss = context.args[1]
            if stopLoss.endswith('%'):
                if call.price <= Decimal("0.0"):
                    await update.message.reply_text(f"Call ID {callId} has no price, try again later when the price is received from the exchange.")
                    return
                stopLoss = call.entryPrice * (1 - Decimal(stopLoss[:-1]) / 100)
            else:
                stopLoss = Decimal(stopLoss)

            if stopLoss <= Decimal("0.0"):
                await update.message.reply_text(f"Stop loss must be greater than 0.")
                return

            call.stopLoss = stopLoss
            await call.Save()
            await call.SendMessage(f"Update stop loss to: {stopLoss}")
        except Exception as e:
            traceback.print_exc()
            await update.message.reply_text(f"An error occurred while setting the stop loss: {e}")

    async def OnCallStatus(self, update: Update, context: CallbackContext) -> None:
        if not await self.CheckCaller(update, context, False):
            return

        try:
            if context.args:
                try:
                    callId = int(context.args[0])
                    call = await self.__monitor.Get(callId)
                    if call:
                        await update.message.reply_text(BotSettings.EscapeMarkdownV2(call.GetOverview()),
                                                        parse_mode=ParseMode.MARKDOWN_V2)
                    else:
                        await update.message.reply_text(f"Call ID {callId} not found.")
                except ValueError:
                    await update.message.reply_text("Invalid call ID.")
            else:
                openCalls = self.__monitor.GetOpenCalls()
                if not openCalls:
                    msg = "No open calls."
                else:
                    msg = "Open calls:\n\n"
                    for call in openCalls:
                        msg += f"{call.GetOverview()}"
                await update.message.reply_text(BotSettings.EscapeMarkdownV2(msg),
                                                parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            traceback.print_exc()
            await update.message.reply_text(f"An error occurred while fetching the status: {e}")

    async def OnCloseCall(self, update: Update, context: CallbackContext) -> None:
        if not await self.CheckCaller(update, context, True):
            return

        if len(context.args) != 1:
            await update.message.reply_text(BotSettings.EscapeMarkdownV2(f"Usage:\n{self.__methodDocumentation['close']}"), parse_mode=ParseMode.MARKDOWN_V2)
            return
        try:
            callId = int(context.args[0])
            await self.__monitor.CloseCall(callId)
        except Exception as e:
            traceback.print_exc()
            await update.message.reply_text(f"An error occurred while closing the call: {e}")

    async def __PostInit(self, _application: Application) -> None:
        print("Creating tables...")
        await database.Database.Init()
        await database.CreateTables()
        await self.__monitor.Initialize()

    def Run(self) -> None:
        print(f"Starting {BotSettings.GetBotName()} version {__version__}, only listening to group chat: {BotSettings.GetGroupChatId()}")
        self.__application.run_polling()

    async def __PostShutdown(self, application: Application) -> None:
        print("Shutting down...")
        await self.__monitor.Stop()

        await database.Database.Close()
        print("Database connection closed.")

    @classmethod
    def GetInstance(cls) -> "CryptoCallBot":
        if cls.__singelton is None:
            cls.__singelton = cls()
        return cls.__singelton

    async def SendMessage(self, message: str) -> None:
        try:
            await self.__application.bot.send_message(chat_id=BotSettings.GetGroupChatId(),
                                                      text=BotSettings.EscapeMarkdownV2(message),
                                                      parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            traceback.print_exc()