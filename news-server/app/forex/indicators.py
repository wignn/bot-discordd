"""
Technical Analysis Indicators
"""

from typing import List, Optional
import numpy as np

from app.forex.models import OHLC, TechnicalIndicators
from app.core.logging import get_logger


logger = get_logger(__name__)


class TechnicalAnalyzer:
    """Calculate technical analysis indicators"""
    
    @staticmethod
    def calculate_sma(closes: List[float], period: int) -> Optional[float]:
        """Simple Moving Average"""
        if len(closes) < period:
            return None
        return sum(closes[-period:]) / period
    
    @staticmethod
    def calculate_ema(closes: List[float], period: int) -> Optional[float]:
        """Exponential Moving Average"""
        if len(closes) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema
    
    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
        """Relative Strength Index"""
        if len(closes) < period + 1:
            return None
        
        changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        
        gains = [c if c > 0 else 0 for c in changes[-period:]]
        losses = [-c if c < 0 else 0 for c in changes[-period:]]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(
        closes: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """MACD (Moving Average Convergence Divergence)"""
        if len(closes) < slow_period + signal_period:
            return None, None, None
        
        def ema(data: List[float], period: int) -> List[float]:
            result = [data[0]]
            multiplier = 2 / (period + 1)
            for price in data[1:]:
                result.append((price * multiplier) + (result[-1] * (1 - multiplier)))
            return result
        
        ema_fast = ema(closes, fast_period)
        ema_slow = ema(closes, slow_period)
        
        macd_line = [f - s for f, s in zip(ema_fast[slow_period-fast_period:], ema_slow)]
        
        if len(macd_line) < signal_period:
            return None, None, None
        
        signal_line = ema(macd_line, signal_period)
        
        macd = macd_line[-1]
        signal = signal_line[-1]
        histogram = macd - signal
        
        return macd, signal, histogram
    
    @staticmethod
    def calculate_bollinger_bands(
        closes: List[float],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """Bollinger Bands (upper, middle, lower)"""
        if len(closes) < period:
            return None, None, None
        
        recent = closes[-period:]
        middle = sum(recent) / period
        
        variance = sum((x - middle) ** 2 for x in recent) / period
        std = variance ** 0.5
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return upper, middle, lower
    
    @staticmethod
    def calculate_atr(candles: List[OHLC], period: int = 14) -> Optional[float]:
        """Average True Range"""
        if len(candles) < period + 1:
            return None
        
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i-1].close
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        return sum(true_ranges[-period:]) / period
    
    @staticmethod
    def calculate_adx(candles: List[OHLC], period: int = 14) -> Optional[float]:
        """Average Directional Index"""
        if len(candles) < period * 2:
            return None
        
        plus_dm = []
        minus_dm = []
        tr_list = []
        
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_high = candles[i-1].high
            prev_low = candles[i-1].low
            prev_close = candles[i-1].close
            
            # Directional Movement
            up_move = high - prev_high
            down_move = prev_low - low
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0)
            
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0)
            
            # True Range
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_list.append(tr)
        
        if len(tr_list) < period:
            return None
        
        # Smoothed values
        atr = sum(tr_list[:period])
        plus_di = sum(plus_dm[:period])
        minus_di = sum(minus_dm[:period])
        
        for i in range(period, len(tr_list)):
            atr = atr - (atr / period) + tr_list[i]
            plus_di = plus_di - (plus_di / period) + plus_dm[i]
            minus_di = minus_di - (minus_di / period) + minus_dm[i]
        
        if atr == 0:
            return None
        
        plus_di_ratio = (plus_di / atr) * 100
        minus_di_ratio = (minus_di / atr) * 100
        
        di_sum = plus_di_ratio + minus_di_ratio
        if di_sum == 0:
            return None
        
        dx = abs(plus_di_ratio - minus_di_ratio) / di_sum * 100
        
        return dx
    
    @classmethod
    def analyze(cls, candles: List[OHLC], symbol: str) -> TechnicalIndicators:
        """Calculate all technical indicators for given candles"""
        closes = [c.close for c in candles]
        
        # Moving Averages
        sma_20 = cls.calculate_sma(closes, 20)
        sma_50 = cls.calculate_sma(closes, 50)
        sma_200 = cls.calculate_sma(closes, 200)
        ema_12 = cls.calculate_ema(closes, 12)
        ema_26 = cls.calculate_ema(closes, 26)
        
        # RSI
        rsi_14 = cls.calculate_rsi(closes, 14)
        
        # MACD
        macd, macd_signal, macd_histogram = cls.calculate_macd(closes)
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = cls.calculate_bollinger_bands(closes)
        
        # ATR
        atr_14 = cls.calculate_atr(candles, 14)
        
        # ADX
        adx = cls.calculate_adx(candles, 14)
        
        from datetime import datetime
        
        return TechnicalIndicators(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            ema_12=ema_12,
            ema_26=ema_26,
            rsi_14=rsi_14,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
            atr_14=atr_14,
            bollinger_upper=bb_upper,
            bollinger_middle=bb_middle,
            bollinger_lower=bb_lower,
            adx=adx,
        )
