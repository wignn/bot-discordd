import { useState, useEffect, useRef } from 'react';
import { TrendingUp, TrendingDown, Minus, Activity, Wifi, WifiOff } from 'lucide-react';
import './LivePrice.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const WS_URL = import.meta.env.VITE_WS_URL || '';

const SYMBOL_INFO = {
    XAUUSD: { label: 'Gold', icon: '🥇', decimals: 2 },
    EURUSD: { label: 'EUR/USD', icon: '💶', decimals: 5 },
    GBPUSD: { label: 'GBP/USD', icon: '💷', decimals: 5 },
    USDJPY: { label: 'USD/JPY', icon: '💴', decimals: 3 },
    BTCUSDT: { label: 'Bitcoin', icon: '₿', decimals: 2 },
    ETHUSDT: { label: 'Ethereum', icon: 'Ξ', decimals: 2 },
};

export default function LivePrice() {
    const [prices, setPrices] = useState({});
    const [prevPrices, setPrevPrices] = useState({});
    const [isConnected, setIsConnected] = useState(false);
    const [flashSymbol, setFlashSymbol] = useState(null);
    const wsRef = useRef(null);
    const reconnectRef = useRef(null);

    useEffect(() => {
        fetch(`${API_BASE_URL}/api/v1/market/prices`)
            .then(res => res.json())
            .then(data => {
                if (data.prices) {
                    const initial = {};
                    data.prices.forEach(p => {
                        initial[p.symbol] = p;
                    });
                    setPrices(initial);
                }
            })
            .catch(() => { });
    }, []);

    useEffect(() => {
        if (!WS_URL) return;

        const connect = () => {
            const wsUrl = `${WS_URL}/api/v1/stream/ws?client_type=price-ticker&client_id=web-price-${Date.now()}`;
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => setIsConnected(true);

            ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.event === 'market.trade' && msg.data) {
                        const d = msg.data;
                        setPrevPrices(prev => ({
                            ...prev,
                            [d.symbol]: prices[d.symbol]?.price || prev[d.symbol]?.price
                        }));
                        setPrices(prev => ({
                            ...prev,
                            [d.symbol]: {
                                symbol: d.symbol,
                                price: d.price,
                                price_str: d.price_str,
                                direction: d.direction,
                                asset_type: d.asset_type,
                                updated_at: d.trade_time,
                            }
                        }));
                        setFlashSymbol(d.symbol);
                        setTimeout(() => setFlashSymbol(null), 600);
                    }
                } catch { }
            };

            ws.onerror = () => setIsConnected(false);
            ws.onclose = () => {
                setIsConnected(false);
                reconnectRef.current = setTimeout(connect, 3000);
            };
        };

        connect();

        return () => {
            if (wsRef.current) wsRef.current.close();
            if (reconnectRef.current) clearTimeout(reconnectRef.current);
        };
    }, []);

    const getDirection = (symbol, currentPrice) => {
        const prev = prevPrices[symbol]?.price ?? prevPrices[symbol];
        if (!prev || !currentPrice) return 'neutral';
        if (currentPrice > prev) return 'up';
        if (currentPrice < prev) return 'down';
        return 'neutral';
    };

    const symbolOrder = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'BTCUSDT', 'ETHUSDT'];
    const activePrices = symbolOrder.filter(s => prices[s]);

    return (
        <section id="prices" className="live-price">
            <div className="container">
                <div className="section-header">
                    <h2>Live <span className="gradient-text">Prices</span></h2>
                    <p>Real-time market data powered by Infoway</p>
                </div>

                <div className="price-status">
                    {isConnected ? (
                        <span className="status-badge status-live">
                            <Wifi size={14} /> <Activity size={14} /> Live
                        </span>
                    ) : (
                        <span className="status-badge status-offline">
                            <WifiOff size={14} /> Connecting...
                        </span>
                    )}
                </div>

                {activePrices.length === 0 ? (
                    <div className="price-loading">
                        <Activity size={24} className="spin" />
                        <p>Waiting for market data...</p>
                    </div>
                ) : (
                    <div className="price-grid">
                        {activePrices.map(symbol => {
                            const info = SYMBOL_INFO[symbol] || { label: symbol, icon: '📊', decimals: 2 };
                            const data = prices[symbol];
                            const dir = getDirection(symbol, data.price);
                            const isFlashing = flashSymbol === symbol;
                            const formattedPrice = typeof data.price === 'number'
                                ? data.price.toFixed(info.decimals)
                                : data.price_str || data.price;

                            return (
                                <div
                                    key={symbol}
                                    className={`price-card ${dir} ${isFlashing ? 'flash' : ''}`}
                                >
                                    <div className="price-card-header">
                                        <span className="price-icon">{info.icon}</span>
                                        <div className="price-label">
                                            <span className="price-symbol">{symbol}</span>
                                            <span className="price-name">{info.label}</span>
                                        </div>
                                        <div className={`price-direction dir-${dir}`}>
                                            {dir === 'up' && <TrendingUp size={16} />}
                                            {dir === 'down' && <TrendingDown size={16} />}
                                            {dir === 'neutral' && <Minus size={16} />}
                                        </div>
                                    </div>
                                    <div className="price-value">
                                        <span className={`price-number dir-${dir}`}>
                                            {data.asset_type === 'crypto' ? '$' : ''}{formattedPrice}
                                        </span>
                                    </div>
                                    <div className="price-meta">
                                        <span className={`price-badge badge-${data.asset_type}`}>
                                            {data.asset_type === 'forex' ? 'FOREX' : 'CRYPTO'}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </section>
    );
}
