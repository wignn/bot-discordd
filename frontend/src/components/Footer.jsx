import { Github, ExternalLink } from 'lucide-react';
import './Footer.css';

export default function Footer() {
    const techStack = [
        { name: 'Rust', color: '#dea584' },
        { name: 'Go', color: '#00add8' },
        { name: 'Python', color: '#3776ab' },
        { name: 'PostgreSQL', color: '#336791' },
        { name: 'Redis', color: '#dc382d' },
        { name: 'Docker', color: '#2496ed' },
    ];

    return (
        <footer className="footer">
            <div className="container">
                <div className="footer-content">
                    <div className="footer-brand">
                        <div className="footer-logo">
                            <span className="footer-logo-icon">✦</span>
                            <h3>Fio</h3>
                        </div>
                        <p>AI-powered trading companion with real-time forex & stock news for Discord.</p>
                    </div>

                    <div className="footer-links">
                        <h4>Navigation</h4>
                        <ul>
                            <li><a href="#features">Features</a></li>
                            <li><a href="#prices">Market</a></li>
                            <li><a href="#news">News Feed</a></li>
                            <li>
                                <a href="https://github.com/wignn/bot-discordd" target="_blank" rel="noopener noreferrer">
                                    GitHub <ExternalLink size={10} />
                                </a>
                            </li>
                        </ul>
                    </div>

                    <div className="footer-tech">
                        <h4>Tech Stack</h4>
                        <div className="tech-tags">
                            {techStack.map((tech) => (
                                <span
                                    key={tech.name}
                                    className="tech-tag"
                                    style={{ '--tech-color': tech.color }}
                                >
                                    {tech.name}
                                </span>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="footer-bottom">
                    <div className="footer-copyright">
                        <span>© 2026 Fio</span>
                        <span className="footer-divider">·</span>
                        <span>Made in Indonesia</span>
                    </div>
                    <a
                        href="https://github.com/wignn/bot-discordd"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="footer-github"
                    >
                        <Github size={16} />
                        <span>View Source</span>
                    </a>
                </div>
            </div>
        </footer>
    );
}
