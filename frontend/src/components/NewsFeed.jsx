import { useState } from 'react';
import { ExternalLink, Clock, TrendingUp, TrendingDown, Minus, Wifi, WifiOff } from 'lucide-react';
import { useNewsWebSocket } from '../hooks/useWebSocket';
import './NewsFeed.css';

export default function NewsFeed() {
    const { forexNews, stockNews, isConnected } = useNewsWebSocket();
    const [activeTab, setActiveTab] = useState('forex');

    const formatTime = (timestamp) => {
        if (!timestamp) return 'N/A';
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    const getSentimentIcon = (sentiment) => {
        switch (sentiment) {
            case 'bullish':
                return <TrendingUp size={12} className="sentiment-bullish" />;
            case 'bearish':
                return <TrendingDown size={12} className="sentiment-bearish" />;
            default:
                return <Minus size={12} className="sentiment-neutral" />;
        }
    };

    const getImpactClass = (impact) => {
        switch (impact) {
            case 'high':
                return 'impact-high';
            case 'medium':
                return 'impact-medium';
            default:
                return 'impact-low';
        }
    };

    const currentNews = activeTab === 'forex' ? forexNews : stockNews;

    if (forexNews.length === 0 && stockNews.length === 0) {
        return (
            <section id="news" className="news-feed">
                <div className="container">
                    <div className="section-header">
                        <h2>Latest <span className="gradient-text">News</span></h2>
                        <p>Real-time forex & stock news delivered to your Discord server</p>
                    </div>
                    <div className="news-empty">
                        <p>Connecting to news feed...</p>
                    </div>
                </div>
            </section>
        );
    }

    return (
        <section id="news" className="news-feed">
            <div className="container">
                <div className="section-header">
                    <h2>Latest <span className="gradient-text">News</span></h2>
                    <p>Real-time forex & stock news delivered to your Discord server</p>
                </div>

                <div className="news-tabs">
                    <button
                        className={`news-tab ${activeTab === 'forex' ? 'active' : ''}`}
                        onClick={() => setActiveTab('forex')}
                    >
                        Forex News
                        {forexNews.length > 0 && <span className="tab-count">{forexNews.length}</span>}
                    </button>
                    <button
                        className={`news-tab ${activeTab === 'stock' ? 'active' : ''}`}
                        onClick={() => setActiveTab('stock')}
                    >
                        Stock News
                        {stockNews.length > 0 && <span className="tab-count">{stockNews.length}</span>}
                    </button>
                </div>

                <div className="news-status">
                    {isConnected ? (
                        <>
                            <Wifi size={14} className="status-online" />
                            <span>Connected to live feed</span>
                        </>
                    ) : (
                        <>
                            <WifiOff size={14} className="status-offline" />
                            <span>Polling mode</span>
                        </>
                    )}
                </div>

                <div className="news-list">
                    {currentNews.length === 0 ? (
                        <div className="news-empty">
                            <p>No {activeTab} news available yet</p>
                        </div>
                    ) : (
                        currentNews.map((article, index) => (
                            <article
                                key={article.id}
                                className="news-item"
                                style={{ animationDelay: `${index * 0.08}s` }}
                            >
                                <div className="news-meta">
                                    <span className="news-source">{article.source}</span>
                                    <span className="news-time">
                                        <Clock size={11} />
                                        {formatTime(article.timestamp)}
                                    </span>
                                </div>

                                <h3 className="news-title">{article.title}</h3>
                                <p className="news-summary">{article.summary}</p>

                                <div className="news-footer">
                                    <div className="news-tags">
                                        <span className={`news-impact ${getImpactClass(article.impact)}`}>
                                            {article.impact || 'low'}
                                        </span>
                                        <span className="news-sentiment">
                                            {getSentimentIcon(article.sentiment)}
                                            {article.sentiment || 'neutral'}
                                        </span>
                                    </div>

                                    {/* Forex pairs */}
                                    {activeTab === 'forex' && article.pairs && article.pairs.length > 0 && (
                                        <div className="news-pairs">
                                            {article.pairs.slice(0, 3).map((pair, i) => (
                                                <span key={i} className="news-pair">{pair}</span>
                                            ))}
                                        </div>
                                    )}

                                    {/* Stock tickers */}
                                    {activeTab === 'stock' && article.tickers && article.tickers.length > 0 && (
                                        <div className="news-pairs">
                                            {article.tickers.slice(0, 4).map((ticker, i) => (
                                                <span key={i} className="news-pair ticker">{ticker}</span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </article>
                        ))
                    )}
                </div>
            </div>
        </section>
    );
}
