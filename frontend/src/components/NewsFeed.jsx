import { ExternalLink, Clock, TrendingUp, TrendingDown, Minus, Wifi, WifiOff } from 'lucide-react';
import { useNewsWebSocket } from '../hooks/useWebSocket';
import './NewsFeed.css';

export default function NewsFeed() {
    const { news, isConnected } = useNewsWebSocket();

    const formatTime = (timestamp) => {
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

    if (news.length === 0) {
        return (
            <section id="news" className="news-feed">
                <div className="container">
                    <div className="section-header">
                        <h2>Latest <span className="gradient-text">News</span></h2>
                        <p>Real-time forex news delivered to your Discord server</p>
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
                    <p>Real-time forex news delivered to your Discord server</p>
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
                    {news.map((article, index) => (
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
                                        {article.impact}
                                    </span>
                                    <span className="news-sentiment">
                                        {getSentimentIcon(article.sentiment)}
                                        {article.sentiment}
                                    </span>
                                </div>
                                {article.pairs && article.pairs.length > 0 && (
                                    <div className="news-pairs">
                                        {article.pairs.slice(0, 3).map((pair, i) => (
                                            <span key={i} className="news-pair">{pair}</span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </article>
                    ))}
                </div>
            </div>
        </section>
    );
}
