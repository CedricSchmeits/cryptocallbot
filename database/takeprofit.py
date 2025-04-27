from .basemodel import BaseModel
from enum import Enum, auto

class TakeProfit(BaseModel):

    """TakeProfit model mapped to the 'takeprofit' table in MySQL."""
    _tableName = "takeprofit"
    _fieldDefinitions = {
        "id": "BIGINT AUTO_INCREMENT PRIMARY KEY",
        "callId": "BIGINT NOT NULL",
        "amount": "DECIMAL(20, 10) NOT NULL",
        "targetPrice": "DECIMAL(20, 10) NOT NULL",
        "result": "DECIMAL(20, 10) DEFAULT '0.0'",
        "triggeredAt": "DATETIME DEFAULT NULL",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
