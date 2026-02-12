import { useState, useEffect } from 'react';
import { Menu, X } from 'lucide-react';
import './Navbar.css';

export default function Navbar() {
    const [scrolled, setScrolled] = useState(false);
    const [menuOpen, setMenuOpen] = useState(false);

    useEffect(() => {
        const onScroll = () => setScrolled(window.scrollY > 40);
        window.addEventListener('scroll', onScroll, { passive: true });
        return () => window.removeEventListener('scroll', onScroll);
    }, []);

    const links = [
        { label: 'Features', href: '#features' },
        { label: 'Market', href: '#prices' },
        { label: 'News', href: '#news' },
    ];

    return (
        <nav className={`navbar ${scrolled ? 'navbar-scrolled' : ''}`}>
            <div className="container navbar-inner">
                <a href="#" className="navbar-brand">
                    <span className="brand-icon">✦</span>
                    <span className="brand-text">Fio</span>
                </a>

                <div className={`navbar-links ${menuOpen ? 'open' : ''}`}>
                    {links.map(link => (
                        <a
                            key={link.href}
                            href={link.href}
                            className="nav-link"
                            onClick={() => setMenuOpen(false)}
                        >
                            {link.label}
                        </a>
                    ))}
                    <a
                        href="https://github.com/wignn/bot-discordd"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="nav-link nav-link-external"
                    >
                        GitHub
                    </a>
                </div>

                <button
                    className="navbar-toggle"
                    onClick={() => setMenuOpen(!menuOpen)}
                    aria-label="Toggle menu"
                >
                    {menuOpen ? <X size={20} /> : <Menu size={20} />}
                </button>
            </div>
        </nav>
    );
}
