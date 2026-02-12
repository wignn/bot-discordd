import { Info, TrendingUp, BarChart3, Calendar } from 'lucide-react';
import './LivePrice.css';

export default function LivePrice() {
    return (
        <section id="prices" className="live-price">
            <div className="container">
                <div className="section-header">
                    <h2>Market <span className="gradient-text">Overview</span></h2>
                    <p>Stay updated with the latest market information</p>
                </div>

                <div className="price-notice">
                    <Info size={20} />
                    <div>
                        <h3>Real-time Prices Coming Soon</h3>
                        <p>
                            Live forex price feeds are being integrated.
                            Check out the real-time news section below!
                        </p>
                    </div>
                </div>

                <div className="market-cards">
                    <div className="market-card" style={{ '--card-accent': '#8b5cf6' }}>
                        <div className="market-card-icon">
                            <TrendingUp size={20} />
                        </div>
                        <h3>Forex News</h3>
                        <p>Real-time forex market news and analysis delivered to your Discord</p>
                    </div>
                    <div className="market-card" style={{ '--card-accent': '#06b6d4' }}>
                        <div className="market-card-icon">
                            <BarChart3 size={20} />
                        </div>
                        <h3>Stock News</h3>
                        <p>Indonesian stock market news with ticker alerts</p>
                    </div>
                    <div className="market-card" style={{ '--card-accent': '#34d399' }}>
                        <div className="market-card-icon">
                            <Calendar size={20} />
                        </div>
                        <h3>Calendar</h3>
                        <p>Economic calendar with high-impact event reminders</p>
                    </div>
                </div>
            </div>
        </section>
    );
}
