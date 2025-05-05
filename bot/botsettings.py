from dotenv import load_dotenv
import os
from telegram import Update
from telegram.ext import ContextTypes
from enum import Enum, auto

load_dotenv()

print(f"BotSettings: {os.getenv('TELEGRAM_BOT_NAME')}, {os.getenv('TELEGRAM_GROUP_CHAT_ID')}, {os.getenv('TELEGRAM_BOT_TOKEN')}")


class MemberStatus(Enum):
    BANNED = auto()
    LEFT = auto()
    RESTRICTED = auto()
    MEMBER = auto()
    ADMINISTRATOR = auto()
    OWNER = auto()

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            value = value.upper()
            for member in cls:
                if member.name == value:
                    return member
        return None

    def __le__(self, other):
        if not isinstance(other, MemberStatus):
            other = MemberStatus(other)
        return self.value <= other.value

    def __lt__(self, other):
        if not isinstance(other, MemberStatus):
            other = MemberStatus(other)
        return self.value < other.value

    def __ge__(self, other):
        if not isinstance(other, MemberStatus):
            other = MemberStatus(other)
        return self.value >= other.value

    def __gt__(self, other):
        if not isinstance(other, MemberStatus):
            other = MemberStatus(other)
        return self.value > other.value


class BotSettings:
    __groupChatId = int(os.getenv('TELEGRAM_GROUP_CHAT_ID'))
    __token = os.getenv('TELEGRAM_BOT_TOKEN')
    __name = os.getenv('TELEGRAM_BOT_NAME')
    __minStatusLevel = MemberStatus(os.getenv('TELEGRAM_BOT_MIN_STATUS_LEVEL', 'RESTRICTED'))
    __minCommandLevel = MemberStatus(os.getenv('TELEGRAM_BOT_MIN_COMMAND_LEVEL', 'MEMBER'))

    @classmethod
    async def IsFromMember(cls, update: Update, context: ContextTypes.DEFAULT_TYPE, isCommand: bool = True) -> bool:
        try:
            member = await context.bot.get_chat_member(chat_id=cls.__groupChatId, user_id=update.effective_user.id)
            minStatusLevel = cls.__minCommandLevel if isCommand else cls.__minStatusLevel
            return MemberStatus(member.status) >= minStatusLevel
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
