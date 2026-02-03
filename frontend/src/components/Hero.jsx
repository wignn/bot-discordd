import { Sparkles, ArrowRight, Github, ChevronDown } from 'lucide-react';
import './Hero.css';

export default function Hero() {
    return (
        <section className="hero">
            {/* Animated Background */}
            <div className="hero-bg">
                <div className="hero-grid"></div>
                <div className="hero-glow"></div>
                <div className="hero-particles">
                    {[...Array(15)].map((_, i) => (
                        <div key={i} className="particle" style={{
                            '--delay': `${Math.random() * 5}s`,
                            '--x': `${Math.random() * 100}%`,
                            '--duration': `${4 + Math.random() * 4}s`
                        }}></div>
                    ))}
                </div>
            </div>

            <div className="container hero-content">
                {/* Badge */}
                <div className="hero-badge animate-fade-in">
                    <Sparkles size={14} />
                    <span>Private Trading Bot</span>
                </div>

                {/* Title */}
                <h1 className="hero-title animate-fade-in" style={{ animationDelay: '0.1s' }}>
                    Real-time Forex News
                    <br />
                    <span className="gradient-text">Delivered to Discord</span>
                </h1>

                {/* Description */}
                <p className="hero-description animate-fade-in" style={{ animationDelay: '0.2s' }}>
                    Automated forex news monitoring with instant Discord notifications,
                    live gold prices, chart analysis, and AI-powered insights.
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
                        <span className="stat-value">6+</span>
                        <span className="stat-label">News Sources</span>
                    </div>
                    <div className="stat-divider"></div>
                    <div className="stat">
                        <span className="stat-value">24/7</span>
                        <span className="stat-label">Uptime</span>
                    </div>
                    <div className="stat-divider"></div>
                    <div className="stat">
                        <span className="stat-value">Rust</span>
                        <span className="stat-label">Performance</span>
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
