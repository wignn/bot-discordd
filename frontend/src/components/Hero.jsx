import { Sparkles, ArrowRight, Github, ChevronDown } from 'lucide-react';
import './Hero.css';

export default function Hero() {
    return (
        <section className="hero">
            {/* Animated Background */}
            <div className="hero-bg">
                <div className="hero-mesh"></div>
                <div className="hero-orb hero-orb-1"></div>
                <div className="hero-orb hero-orb-2"></div>
                <div className="hero-orb hero-orb-3"></div>
                <div className="hero-particles">
                    {[...Array(20)].map((_, i) => (
                        <div key={i} className="particle" style={{
                            '--delay': `${Math.random() * 6}s`,
                            '--x': `${Math.random() * 100}%`,
                            '--duration': `${5 + Math.random() * 5}s`,
                            '--size': `${2 + Math.random() * 3}px`
                        }}></div>
                    ))}
                </div>
            </div>

            <div className="container hero-content">
                {/* Badge */}
                <div className="hero-badge animate-fade-in">
                    <Sparkles size={14} />
                    <span>Fio Trading Assistant</span>
                </div>

                {/* Title */}
                <h1 className="hero-title animate-fade-in" style={{ animationDelay: '0.1s' }}>
                    Your AI-Powered
                    <br />
                    <span className="gradient-text">Trading Companion</span>
                </h1>

                {/* Description */}
                <p className="hero-description animate-fade-in" style={{ animationDelay: '0.2s' }}>
                    Real-time forex & stock news, live prices, chart analysis, and
                    AI-powered insights — all delivered instantly to your Discord server.
                </p>

                {/* CTAs */}
                <div className="hero-actions animate-fade-in" style={{ animationDelay: '0.3s' }}>
                    <a href="#features" className="btn btn-primary">
                        <span>Explore Features</span>
                        <ArrowRight size={16} />
                    </a>
                    <a
                        href="https://github.com/wignn/bot-discordd"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-secondary"
                    >
                        <Github size={16} />
                        <span>Source Code</span>
                    </a>
                </div>

                {/* Stats */}
                <div className="hero-stats animate-fade-in" style={{ animationDelay: '0.4s' }}>
                    <div className="stat">
                        <span className="stat-value">AI</span>
                        <span className="stat-label">Powered</span>
                    </div>
                    <div className="stat-divider"></div>
                    <div className="stat">
                        <span className="stat-value">Real-time</span>
                        <span className="stat-label">News Feed</span>
                    </div>
                    <div className="stat-divider"></div>
                    <div className="stat">
                        <span className="stat-value">24/7</span>
                        <span className="stat-label">Active</span>
                    </div>
                </div>
            </div>

            {/* Scroll Indicator */}
            <a href="#features" className="scroll-indicator">
                <ChevronDown size={20} />
            </a>
        </section>
    );
}
