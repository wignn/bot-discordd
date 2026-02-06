import { useState, useEffect, useRef, useCallback } from 'react';

// Configuration - will use relative paths when deployed behind same domain
const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const WS_URL = import.meta.env.VITE_WS_URL || '';

// Custom hook for WebSocket connection to news feed
export function useNewsWebSocket() {
    const [forexNews, setForexNews] = useState([]);
    const [stockNews, setStockNews] = useState([]);
    const [isConnected, setIsConnected] = useState(false);
    const [error, setError] = useState(null);
    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);

    // Fetch initial forex news via REST API
    const fetchLatestNews = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/news/latest?limit=10`);
            if (response.ok) {
                const data = await response.json();
                if (data.items && data.items.length > 0) {
                    setForexNews(data.items.map(item => ({
                        id: item.id,
                        title: item.translated_title || item.original_title,
                        summary: item.summary,
                        source: item.source_name,
                        timestamp: item.published_at,
                        sentiment: item.sentiment,
                        impact: item.impact_level,
                        pairs: item.currency_pairs || []
                    })));
                }
            }
        } catch (e) {
            console.error('Failed to fetch forex news:', e);
        }
    }, []);

    // Fetch initial stock news via REST API
    const fetchLatestStockNews = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/stock/latest?limit=10`);
            if (response.ok) {
                const data = await response.json();
                if (data.items && data.items.length > 0) {
                    setStockNews(data.items.map(item => ({
                        id: item.id || item.content_hash,
                        title: item.title,
                        summary: item.summary,
                        source: item.source_name,
                        timestamp: item.published_at || item.processed_at,
                        sentiment: item.sentiment,
                        impact: item.impact_level,
                        tickers: item.tickers ? item.tickers.split(',') : [],
                        category: item.category
                    })));
                }
            }
        } catch (e) {
            console.error('Failed to fetch stock news:', e);
        }
    }, []);

    const connect = useCallback(() => {
        if (!WS_URL) {
            // Fallback to REST polling if no WebSocket URL
            fetchLatestNews();
            fetchLatestStockNews();
            const interval = setInterval(() => {
                fetchLatestNews();
                fetchLatestStockNews();
            }, 30000);
            return () => clearInterval(interval);
        }

        try {
            const wsUrl = `${WS_URL}/api/v1/stream/ws?client_type=web&client_id=web-${Date.now()}`;
            wsRef.current = new WebSocket(wsUrl);

            wsRef.current.onopen = () => {
                setIsConnected(true);
                setError(null);
                fetchLatestNews();
                fetchLatestStockNews();
            };

            wsRef.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const eventType = data.event || data.type;

                    if (eventType === 'news.new' || eventType === 'news.high_impact') {
                        const article = data.data?.article || data.data;
                        if (article) {
                            setForexNews(prev => [{
                                id: article.id,
                                title: article.title_id || article.title,
                                summary: article.summary_id || article.summary,
                                source: article.source_name,
                                timestamp: article.published_at || article.processed_at,
                                sentiment: article.sentiment,
                                impact: article.impact_level,
                                pairs: article.currency_pairs || []
                            }, ...prev].slice(0, 15));
                        }
                    }

                    // Handle stock news
                    if (eventType === 'stock.news.new' || eventType === 'stock.news.high_impact') {
                        const article = data.data?.article || data.data;
                        if (article) {
                            setStockNews(prev => [{
                                id: article.id,
                                title: article.title,
                                summary: article.summary,
                                source: article.source_name,
                                timestamp: article.published_at || article.processed_at,
                                sentiment: article.sentiment,
                                impact: article.impact_level,
                                tickers: article.tickers || [],
                                category: article.category
                            }, ...prev].slice(0, 15));
                        }
                    }
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };

            wsRef.current.onerror = () => {
                setError('Connection error');
                setIsConnected(false);
            };

            wsRef.current.onclose = () => {
                setIsConnected(false);
                reconnectTimeoutRef.current = setTimeout(connect, 5000);
            };
        } catch (e) {
            setError('Failed to connect');
            fetchLatestNews();
            fetchLatestStockNews();
        }
    }, [fetchLatestNews, fetchLatestStockNews]);

    useEffect(() => {
        connect();

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
        };
    }, [connect]);

    // Combined news for backward compatibility
    const news = forexNews;

    return { news, forexNews, stockNews, isConnected, error };
}
