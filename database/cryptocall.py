from .basemodel import BaseModel
from enum import Enum, auto
from decimal import Decimal, getcontext

getcontext().prec = 20  # Set precision for Decimal operations

class CryptoCall(BaseModel):
    class Status(Enum):
        ACQUIRING = 0
        ACTIVE = 1
        CLOSED = 2

    """CryptoCall model mapped to the 'crypto_call' table in MySQL."""
    _tableName = "crypto_call"
    _fieldDefinitions = {
        "id": "BIGINT AUTO_INCREMENT PRIMARY KEY",
        "pair": "VARCHAR(30) NOT NULL",
        "entryPrice": "DECIMAL(20, 10) NOT NULL",
        "stopLoss": "DECIMAL(20, 10) NOT NULL",
        "investment": "DECIMAL(20, 10) DEFAULT '100.0'",
        "amount": "DECIMAL(20, 10) DEFAULT '0.0'",
        "result": "DECIMAL(20, 10) DEFAULT '0.0'",
        "profit": "DECIMAL(20, 10) DEFAULT '0.0'",
        "createdAt": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        "activatedAt": "DATETIME DEFAULT NULL",
        "stopLossTriggered": "DATETIME DEFAULT NULL",
        "closedAt": "DATETIME DEFAULT NULL",
        "status": "ENUM('acquiring', 'active', 'closed') NOT NULL DEFAULT 'acquiring'"
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
