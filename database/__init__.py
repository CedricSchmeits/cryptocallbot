from .database import Database
from .cryptocall import CryptoCall
from .takeprofit import TakeProfit

__all__ = ["Database", "CreateTables", "CryptoCall", "TakeProfit"]


async def CreateTables():
    """Create all tables in the database."""
    await CryptoCall.CreateTable()
    await TakeProfit.CreateTable()
