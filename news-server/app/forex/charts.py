"""
Forex Chart Generator

Generates candlestick charts, line charts, and technical analysis visualizations.
TradingView-inspired dark theme styling.
"""

import io
import base64
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Literal

import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.lines import Line2D
import numpy as np

from app.forex.models import OHLC, ForexPrice, TechnicalIndicators
from app.core.logging import get_logger


logger = get_logger(__name__)

COLORS = {
    "background": "#131722",      
    "chart_bg": "#1e222d",        
    "grid": "#363c4e",            
    "grid_light": "#2a2e39",      
    "text": "#d1d4dc",            
    "text_dim": "#787b86",      
    "text_bright": "#ffffff",    
    "bullish": "#26a69a",         
    "bullish_wick": "#26a69a",
    "bearish": "#ef5350",        
    "bearish_wick": "#ef5350",
    "line": "#2962ff",           
    "ma_fast": "#f7a21b",         
    "ma_slow": "#2962ff",        
    "ma_200": "#e91e63",         
    "ema": "#00bcd4",             
    "volume_up": "#26a69a80",     
    "volume_down": "#ef535080",   
    "bollinger_upper": "#9c27b0",
    "bollinger_lower": "#9c27b0", 
    "bollinger_fill": "#9c27b020",
    "price_line": "#2962ff",
    "price_label_bg": "#2962ff",
    "crosshair": "#758696",
    "annotation_bg": "#2a2e39",
    
    # Comparison colors
    "compare_1": "#2962ff",       # Blue
    "compare_2": "#f7a21b",       # Orange
    "compare_3": "#e91e63",       # Pink
    "compare_4": "#26a69a",       # Teal
    "compare_5": "#9c27b0",       # Purple
    "compare_6": "#00bcd4",       # Cyan
}


class ChartGenerator:
    """Generate forex charts with TradingView-style appearance"""
    
    def __init__(self):
        plt.style.use('dark_background')
        matplotlib.rcParams.update({
            'font.family': 'sans-serif',
            'font.sans-serif': ['Trebuchet MS', 'Segoe UI', 'Arial', 'sans-serif'],
            'font.size': 10,
            'axes.titlesize': 13,
            'axes.labelsize': 10,
            'axes.titleweight': 'normal',
            'axes.edgecolor': COLORS["grid"],
            'axes.linewidth': 0.5,
            'xtick.color': COLORS["text_dim"],
            'ytick.color': COLORS["text_dim"],
            'xtick.labelsize': 9,
            'ytick.labelsize': 9,
            'legend.fontsize': 9,
            'legend.framealpha': 0.8,
            'figure.facecolor': COLORS["background"],
            'axes.facecolor': COLORS["chart_bg"],
            'savefig.facecolor': COLORS["background"],
            'savefig.edgecolor': COLORS["background"],
        })
    
    def generate_candlestick_chart(
        self,
        candles: List[OHLC],
        symbol: str,
        timeframe: str = "1h",
        show_volume: bool = False,
        show_ma: bool = True,
        ma_periods: Tuple[int, int] = (20, 50),
        width: int = 12,
        height: int = 6,
        output_format: Literal["base64", "bytes"] = "base64",
    ) -> Optional[str | bytes]:
        if not candles or len(candles) < 2:
            logger.warning("Not enough candles for chart generation")
            return None
        
        try:
            # Create figure with TradingView styling
            fig, ax = plt.subplots(figsize=(width, height), facecolor=COLORS["background"])
            ax.set_facecolor(COLORS["chart_bg"])
            
            # Prepare data
            dates = [c.timestamp for c in candles]
            opens = [c.open for c in candles]
            highs = [c.high for c in candles]
            lows = [c.low for c in candles]
            closes = [c.close for c in candles]
            
            # Calculate candle width based on data
            if len(dates) > 1:
                avg_interval = (dates[-1] - dates[0]).total_seconds() / len(dates)
                candle_width = avg_interval / 86400 * 0.7 
            else:
                candle_width = 0.0005
            
            for i, candle in enumerate(candles):
                date_num = mdates.date2num(candle.timestamp)
                is_bullish = candle.is_bullish
                body_color = COLORS["bullish"] if is_bullish else COLORS["bearish"]
                wick_color = COLORS["bullish_wick"] if is_bullish else COLORS["bearish_wick"]
                ax.plot(
                    [date_num, date_num],
                    [candle.low, candle.high],
                    color=wick_color,
                    linewidth=1,
                    solid_capstyle='round',
                )
                
                body_bottom = min(candle.open, candle.close)
                body_height = abs(candle.close - candle.open)
                
                rect = Rectangle(
                    (date_num - candle_width / 2, body_bottom),
                    candle_width,
                    body_height if body_height > 0 else 0.00001,
                    facecolor=body_color,
                    edgecolor=body_color,
                    linewidth=0.5,
                )
                ax.add_patch(rect)
            
            if show_ma and len(candles) >= ma_periods[0]:
                closes_array = np.array(closes)
                
                if len(closes_array) >= ma_periods[0]:
                    ma_fast = self._calculate_sma(closes_array, ma_periods[0])
                    valid_dates = dates[ma_periods[0]-1:]
                    ax.plot(
                        valid_dates,
                        ma_fast,
                        color=COLORS["ma_fast"],
                        linewidth=1.2,
                        label=f"MA {ma_periods[0]}",
                    )
                
                if len(closes_array) >= ma_periods[1]:
                    ma_slow = self._calculate_sma(closes_array, ma_periods[1])
                    valid_dates = dates[ma_periods[1]-1:]
                    ax.plot(
                        valid_dates,
                        ma_slow,
                        color=COLORS["ma_slow"],
                        linewidth=1.2,
                        label=f"MA {ma_periods[1]}",
                    )
                
                legend = ax.legend(
                    loc="upper left", 
                    frameon=True,
                    fancybox=False,
                    edgecolor=COLORS["grid"],
                    facecolor=COLORS["chart_bg"],
                    labelcolor=COLORS["text_dim"],
                )
            
            ax.text(
                0.01, 0.98,
                f"{symbol.upper()}",
                transform=ax.transAxes,
                fontsize=14,
                fontweight='bold',
                color=COLORS["text_bright"],
                verticalalignment='top',
            )
            
            ax.text(
                0.01, 0.91,
                f"{timeframe}",
                transform=ax.transAxes,
                fontsize=10,
                color=COLORS["text_dim"],
                verticalalignment='top',
            )
            
            price_change = closes[-1] - opens[0]
            price_change_pct = (price_change / opens[0]) * 100
            change_color = COLORS["bullish"] if price_change >= 0 else COLORS["bearish"]
            change_sign = "+" if price_change >= 0 else ""

            ohlc_text = f"O {opens[-1]:.5f}  H {highs[-1]:.5f}  L {lows[-1]:.5f}  C {closes[-1]:.5f}"
            ax.text(
                0.12, 0.98,
                ohlc_text,
                transform=ax.transAxes,
                fontsize=9,
                color=COLORS["text_dim"],
                verticalalignment='top',
                family='monospace',
            )
            
            ax.text(
                0.12, 0.91,
                f"{change_sign}{price_change:.5f} ({change_sign}{price_change_pct:.2f}%)",
                transform=ax.transAxes,
                fontsize=10,
                color=change_color,
                fontweight='bold',
                verticalalignment='top',
            )
            
            ax.set_xlabel("")
            ax.set_ylabel("")
            
            ax.grid(True, color=COLORS["grid_light"], alpha=0.5, linestyle='-', linewidth=0.5)
            ax.set_axisbelow(True) 
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %H:%M"))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
            ax.yaxis.tick_right()
            ax.yaxis.set_label_position("right")
            
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.5f}'))
            if closes:
                current_price = closes[-1]
                
                ax.axhline(
                    y=current_price, 
                    color=COLORS["price_line"], 
                    linestyle='--', 
                    linewidth=1,
                    alpha=0.7
                )
                ax.annotate(
                    f"{current_price:.5f}",
                    xy=(1.0, current_price),
                    xycoords=("axes fraction", "data"),
                    fontsize=9,
                    color=COLORS["text_bright"],
                    fontweight='bold',
                    verticalalignment="center",
                    horizontalalignment="left",
                    bbox=dict(
                        boxstyle='square,pad=0.3',
                        facecolor=COLORS["price_label_bg"],
                        edgecolor='none',
                    ),
                )
            
            for spine in ax.spines.values():
                spine.set_color(COLORS["grid"])
                spine.set_linewidth(0.5)
            
            plt.tight_layout()
            plt.subplots_adjust(right=0.92)  
            
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, facecolor=COLORS["background"], 
                       edgecolor='none', bbox_inches='tight', pad_inches=0.1)
            buf.seek(0)
            plt.close(fig)
            
            if output_format == "base64":
                return base64.b64encode(buf.getvalue()).decode("utf-8")
            return buf.getvalue()
            
        except Exception as e:
            logger.error("Chart generation failed", error=str(e))
            plt.close("all")
            return None
    
    def generate_line_chart(
        self,
        prices: List[ForexPrice],
        symbol: str,
        width: int = 12,
        height: int = 6,
        output_format: Literal["base64", "bytes"] = "base64",
    ) -> Optional[str | bytes]:
        """Generate a TradingView-style line chart from price data"""
        if not prices or len(prices) < 2:
            return None
        
        try:
            fig, ax = plt.subplots(figsize=(width, height), facecolor=COLORS["background"])
            ax.set_facecolor(COLORS["chart_bg"])
            
            dates = [p.timestamp for p in prices]
            mids = [p.mid for p in prices]
            
            is_bullish = mids[-1] >= mids[0]
            line_color = COLORS["bullish"] if is_bullish else COLORS["bearish"]
            
            ax.plot(dates, mids, color=line_color, linewidth=2, solid_capstyle='round')
            
            ax.fill_between(
                dates, 
                mids, 
                min(mids),
                alpha=0.15, 
                color=line_color,
            )
            
            ax.text(
                0.01, 0.98,
                f"{symbol.upper()}",
                transform=ax.transAxes,
                fontsize=14,
                fontweight='bold',
                color=COLORS["text_bright"],
                verticalalignment='top',
            )
            
            change = mids[-1] - mids[0]
            change_pct = (change / mids[0]) * 100
            change_sign = "+" if change >= 0 else ""
            
            ax.text(
                0.01, 0.90,
                f"{mids[-1]:.5f}",
                transform=ax.transAxes,
                fontsize=18,
                fontweight='bold',
                color=COLORS["text_bright"],
                verticalalignment='top',
                family='monospace',
            )
            
            ax.text(
                0.01, 0.78,
                f"{change_sign}{change:.5f} ({change_sign}{change_pct:.2f}%)",
                transform=ax.transAxes,
                fontsize=11,
                color=line_color,
                fontweight='bold',
                verticalalignment='top',
            )
            
            ax.grid(True, color=COLORS["grid_light"], alpha=0.5, linestyle='-', linewidth=0.5)
            ax.set_axisbelow(True)
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.yaxis.tick_right()
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.5f}'))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
            current_price = mids[-1]
            ax.axhline(y=current_price, color=COLORS["price_line"], linestyle='--', linewidth=1, alpha=0.7)
            ax.annotate(
                f"{current_price:.5f}",
                xy=(1.0, current_price),
                xycoords=("axes fraction", "data"),
                fontsize=9,
                color=COLORS["text_bright"],
                fontweight='bold',
                verticalalignment="center",
                horizontalalignment="left",
                bbox=dict(
                    boxstyle='square,pad=0.3',
                    facecolor=COLORS["price_label_bg"],
                    edgecolor='none',
                ),
            )
            
            for spine in ax.spines.values():
                spine.set_color(COLORS["grid"])
                spine.set_linewidth(0.5)
            
            plt.tight_layout()
            plt.subplots_adjust(right=0.92)
            
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, facecolor=COLORS["background"],
                       edgecolor='none', bbox_inches='tight', pad_inches=0.1)
            buf.seek(0)
            plt.close(fig)
            
            if output_format == "base64":
                return base64.b64encode(buf.getvalue()).decode("utf-8")
            return buf.getvalue()
            
        except Exception as e:
            logger.error("Line chart generation failed", error=str(e))
            plt.close("all")
            return None
    
    def generate_multi_pair_chart(
        self,
        data: dict[str, List[ForexPrice]],
        width: int = 12,
        height: int = 6,
        output_format: Literal["base64", "bytes"] = "base64",
    ) -> Optional[str | bytes]:
        if not data:
            return None
        
        try:
            fig, ax = plt.subplots(figsize=(width, height), facecolor=COLORS["background"])
            ax.set_facecolor(COLORS["chart_bg"])
            
            compare_colors = [
                COLORS["compare_1"],
                COLORS["compare_2"], 
                COLORS["compare_3"],
                COLORS["compare_4"],
                COLORS["compare_5"],
                COLORS["compare_6"],
            ]
            
            legend_items = []
            
            for i, (symbol, prices) in enumerate(data.items()):
                if len(prices) < 2:
                    continue
                
                dates = [p.timestamp for p in prices]
                mids = [p.mid for p in prices]
                base = mids[0]
                normalized = [(m / base - 1) * 100 for m in mids]
                
                color = compare_colors[i % len(compare_colors)]
                line, = ax.plot(dates, normalized, color=color, linewidth=2, label=symbol.upper())
            
                final_change = normalized[-1]
                change_sign = "+" if final_change >= 0 else ""
                ax.annotate(
                    f"{symbol.upper()} {change_sign}{final_change:.2f}%",
                    xy=(dates[-1], normalized[-1]),
                    xytext=(5, 0),
                    textcoords='offset points',
                    fontsize=9,
                    color=color,
                    fontweight='bold',
                    verticalalignment='center',
                )
            
            ax.axhline(y=0, color=COLORS["text_dim"], linestyle='-', alpha=0.5, linewidth=1)
            
            ax.text(
                0.01, 0.98,
                "COMPARISON",
                transform=ax.transAxes,
                fontsize=14,
                fontweight='bold',
                color=COLORS["text_bright"],
                verticalalignment='top',
            )
            
            ax.text(
                0.01, 0.90,
                "% Change",
                transform=ax.transAxes,
                fontsize=10,
                color=COLORS["text_dim"],
                verticalalignment='top',
            )
            
            ax.set_xlabel("")
            ax.set_ylabel("")
            
            ax.yaxis.tick_right()
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:+.2f}%'))
            
            # Grid
            ax.grid(True, color=COLORS["grid_light"], alpha=0.5, linestyle='-', linewidth=0.5)
            ax.set_axisbelow(True)
            
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')
            
            legend = ax.legend(
                loc="upper left",
                frameon=True,
                fancybox=False,
                edgecolor=COLORS["grid"],
                facecolor=COLORS["chart_bg"],
                labelcolor=COLORS["text"],
                fontsize=9,
            )
            
            for spine in ax.spines.values():
                spine.set_color(COLORS["grid"])
                spine.set_linewidth(0.5)
            
            plt.tight_layout()
            plt.subplots_adjust(right=0.88)  
            
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, facecolor=COLORS["background"],
                       edgecolor='none', bbox_inches='tight', pad_inches=0.1)
            buf.seek(0)
            plt.close(fig)
            
            if output_format == "base64":
                return base64.b64encode(buf.getvalue()).decode("utf-8")
            return buf.getvalue()
            
        except Exception as e:
            logger.error("Multi-pair chart generation failed", error=str(e))
            plt.close("all")
            return None
    
    def _calculate_sma(self, data: np.ndarray, period: int) -> np.ndarray:
        return np.convolve(data, np.ones(period) / period, mode='valid')
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        ema = np.zeros(len(data))
        multiplier = 2 / (period + 1)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        return ema
