import {
    Newspaper,
    TrendingUp,
    BarChart3,
    Music,
    Bot,
    Shield,
    Bell,
    Clock,
    Zap
} from 'lucide-react';
import './Features.css';

const features = [
    {
        icon: Newspaper,
        title: 'Real-time News',
        description: 'Instant forex news from 6+ sources including Reuters, FXStreet, and Investing.com.',
        highlight: true,
        color: '#8b5cf6'
    },
    {
        icon: TrendingUp,
        title: 'Live Prices',
        description: 'Check live forex prices for XAU/USD, EUR/USD, GBP/USD with real-time Tiingo data.',
        highlight: true,
        color: '#06b6d4'
    },
    {
        icon: BarChart3,
        title: 'Chart Analysis',
        description: 'Generate professional candlestick charts with technical indicators via /chart command.',
        color: '#f59e0b'
    },
    {
        icon: Bell,
        title: 'Price Alerts',
        description: 'Set custom price alerts and receive notifications when your target is reached.',
        color: '#34d399'
    },
    {
        icon: Music,
        title: 'Music Player',
        description: 'Full-featured music player with queue management and Spotify integration.',
        color: '#f472b6'
    },
    {
        icon: Bot,
        title: 'AI Assistant',
        description: 'Powered by Gemini AI for trading insights, analysis, and conversation.',
        color: '#a78bfa'
    },
    {
        icon: Shield,
        title: 'Moderation',
        description: 'Complete suite including warn, kick, ban, and timeout commands.',
        color: '#60a5fa'
    },
    {
        icon: Clock,
        title: '24/7 Operation',
        description: 'Deployed on VPS with automatic restart and continuous monitoring.',
        color: '#fbbf24'
    },
    {
        icon: Zap,
        title: 'High Performance',
        description: 'Built with Rust for maximum speed and minimal resource usage.',
        color: '#f87171'
    }
];

export default function Features() {
    return (
        <section id="features" className="features">
            <div className="container">
                <div className="section-header">
                    <h2>Powerful <span className="gradient-text">Features</span></h2>
                    <p>Everything you need for forex trading, packed into one smart Discord bot</p>
                </div>

                <div className="features-grid">
                    {features.map((feature, index) => (
                        <div
                            key={index}
                            className={`feature-card ${feature.highlight ? 'feature-highlight' : ''}`}
                            style={{
                                animationDelay: `${index * 0.05}s`,
                                '--feature-color': feature.color
                            }}
                        >
                            <div className="feature-icon">
                                <feature.icon size={22} strokeWidth={1.5} />
                            </div>
                            <h3>{feature.title}</h3>
                            <p>{feature.description}</p>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
