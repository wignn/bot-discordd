import { useState, useEffect, useRef, useCallback } from 'react';

// Configuration - will use relative paths when deployed behind same domain
const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const WS_URL = import.meta.env.VITE_WS_URL || '';

// Custom hook for WebSocket connection to news feed
export function useNewsWebSocket() {
    const [news, setNews] = useState([]);
    const [isConnected, setIsConnected] = useState(false);
    const [error, setError] = useState(null);
    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);

    // Fetch initial news via REST API
    const fetchLatestNews = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/news/latest?limit=10`);
            if (response.ok) {
                const data = await response.json();
                if (data.items && data.items.length > 0) {
                    setNews(data.items.map(item => ({
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
            console.error('Failed to fetch news:', e);
        }
    }, []);

    const connect = useCallback(() => {
        if (!WS_URL) {
            // Fallback to REST polling if no WebSocket URL
            fetchLatestNews();
            const interval = setInterval(fetchLatestNews, 30000);
            return () => clearInterval(interval);
        }

        try {
            const wsUrl = `${WS_URL}/api/v1/stream/ws?client_type=web&client_id=web-${Date.now()}`;
            wsRef.current = new WebSocket(wsUrl);

            wsRef.current.onopen = () => {
                setIsConnected(true);
                setError(null);
                fetchLatestNews();
            };

            wsRef.current.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'news.new' || data.type === 'news.high_impact') {
                        const article = data.data;
                        setNews(prev => [{
                            id: article.id,
                            title: article.translated_title || article.original_title,
                            summary: article.summary,
                            source: article.source_name,
                            timestamp: article.published_at,
                            sentiment: article.sentiment,
                            impact: article.impact_level,
                            pairs: article.currency_pairs || []
                        }, ...prev].slice(0, 10));
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
        }
    }, [fetchLatestNews]);

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

    return { news, isConnected, error };
}

// Custom hook for live price from Forex service
export function useLivePrice() {
    const [prices, setPrices] = useState({
        xauusd: null,
        eurusd: null,
        gbpusd: null,
    });
    const [lastUpdate, setLastUpdate] = useState(new Date());
    const [isLoading, setIsLoading] = useState(true);

    const fetchPrices = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/forex/prices`);
            if (response.ok) {
                const data = await response.json();

                // Transform API response to our format
                const priceMap = {};
                if (data.prices && Array.isArray(data.prices)) {
                    data.prices.forEach(p => {
                        const symbol = p.symbol.toLowerCase();
                        priceMap[symbol] = {
                            bid: p.bid,
                            ask: p.ask,
                            mid: p.mid,
                            spread: p.spread,
                            spreadPips: p.spread_pips,
                            change: 0, // API doesn't provide change yet
                            changePercent: 0,
                        };
                    });
                }

                setPrices(prev => ({
                    xauusd: priceMap.xauusd || prev.xauusd,
                    eurusd: priceMap.eurusd || prev.eurusd,
                    gbpusd: priceMap.gbpusd || prev.gbpusd,
                }));
                setLastUpdate(new Date());
                setIsLoading(false);
            }
        } catch (e) {
            console.error('Failed to fetch prices:', e);
            // Keep trying but don't overwrite existing data
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchPrices();
        const interval = setInterval(fetchPrices, 5000);
        return () => clearInterval(interval);
    }, [fetchPrices]);

    return { prices, lastUpdate, isLoading };
}
