from dotenv import load_dotenv
import os
from telegram import Update
from telegram.ext import ContextTypes

load_dotenv()

print(f"BotSettings: {os.getenv('TELEGRAM_BOT_NAME')}, {os.getenv('TELEGRAM_GROUP_CHAT_ID')}, {os.getenv('TELEGRAM_BOT_TOKEN')}")

class BotSettings:
    __groupChatId = int(os.getenv('TELEGRAM_GROUP_CHAT_ID'))
    __token = os.getenv('TELEGRAM_BOT_TOKEN')
    __name = os.getenv('TELEGRAM_BOT_NAME')

    @classmethod
    def IsFromGroup(cls, update: Update) -> bool:
        return update.effective_chat.id == cls.__groupChatId

    @classmethod
    async def IsFromMember(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        try:
            member = await context.bot.get_chat_member(chat_id=cls.__groupChatId, user_id=update.effective_user.id)
            return member.status in ["creator", "administrator", "member", "restricted"]
        except Exception as e:
            print(f"Error checking member status: {e}")
            return False

    @classmethod
    def GetGroupChatId(cls) -> int:
        return cls.__groupChatId

    @classmethod
    def GetBotToken(cls) -> str:
        return cls.__token

    @classmethod
    def GetBotName(cls) -> str:
        return cls.__name

    @staticmethod
    def EscapeMarkdownV2(text: str) -> str:
        escapeChars = r'_[]()~>#+-=|{}.!'  # excluding: `*
        return ''.join(f'\\{char}' if char in escapeChars else char for char in text)
