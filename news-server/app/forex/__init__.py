"""
Forex Service Module

Provides real-time forex price data, chart generation, 
technical analysis, and alert management.
"""

from app.forex.service import ForexService
from app.forex.models import ForexPrice, PriceAlert, AlertCondition, OHLC
from app.forex.charts import ChartGenerator

__all__ = [
    "ForexService",
    "ForexPrice",
    "PriceAlert", 
    "AlertCondition",
    "OHLC",
    "ChartGenerator",
]
