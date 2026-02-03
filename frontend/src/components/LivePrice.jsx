import { TrendingUp, TrendingDown, Activity, RefreshCw } from 'lucide-react';
import { useLivePrice } from '../hooks/useWebSocket';
import './LivePrice.css';

export default function LivePrice() {
    const { prices, lastUpdate, isLoading } = useLivePrice();

    const formatPrice = (price, decimals = 5) => {
        if (price === null || price === undefined) return '--';
        return price.toFixed(decimals);
    };

    const formatTime = (date) => {
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    };

    const priceCards = [
        {
            symbol: 'XAU/USD',
            name: 'Gold Spot',
            key: 'xauusd',
            decimals: 2,
            featured: true
        },
        {
            symbol: 'EUR/USD',
            name: 'Euro Dollar',
            key: 'eurusd',
            decimals: 5,
            featured: false
        },
        {
            symbol: 'GBP/USD',
            name: 'Pound Dollar',
            key: 'gbpusd',
            decimals: 5,
            featured: false
        }
    ];

    return (
        <section id="prices" className="live-price">
            <div className="container">
                <div className="section-header">
                    <h2>Live <span className="gradient-text">Prices</span></h2>
                    <p>Real-time forex data powered by Tiingo</p>
                </div>

                <div className="price-grid">
                    {priceCards.map((card) => {
                        const data = prices[card.key];
                        const hasData = data && data.bid;

                        return (
                            <div
                                key={card.symbol}
                                className={`price-card ${card.featured ? 'price-featured' : ''}`}
                            >
                                <div className="price-header">
                                    <div className="price-symbol">
                                        <div className="symbol-badge">{card.symbol.split('/')[0]}</div>
                                        <div>
                                            <h3>{card.symbol}</h3>
                                            <span className="symbol-name">{card.name}</span>
                                        </div>
                                    </div>
                                    {hasData && data.spreadPips && (
                                        <div className="price-spread">
                                            <span>{data.spreadPips.toFixed(1)} pips</span>
                                        </div>
                                    )}
                                </div>

                                <div className="price-values">
                                    <div className="price-main">
                                        <span className="price-current">
                                            {hasData ? formatPrice(data.bid, card.decimals) : '--'}
                                        </span>
                                        {hasData && <span className="price-pulse"></span>}
                                    </div>
                                    <div className="price-details">
                                        <div className="price-detail">
                                            <span className="detail-label">Bid</span>
                                            <span className="detail-value">{hasData ? formatPrice(data.bid, card.decimals) : '--'}</span>
                                        </div>
                                        <div className="price-detail">
                                            <span className="detail-label">Ask</span>
                                            <span className="detail-value">{hasData ? formatPrice(data.ask, card.decimals) : '--'}</span>
                                        </div>
                                        <div className="price-detail">
                                            <span className="detail-label">Mid</span>
                                            <span className="detail-value">{hasData ? formatPrice(data.mid, card.decimals) : '--'}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>

                <div className="price-status">
                    <Activity size={14} className="status-pulse" />
                    <span>Tiingo API</span>
                    <span className="status-divider">|</span>
                    <RefreshCw size={14} />
                    <span>{formatTime(lastUpdate)}</span>
                </div>
            </div>
        </section>
    );
}
