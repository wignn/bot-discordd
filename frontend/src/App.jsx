import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import LivePrice from './components/LivePrice';
import NewsFeed from './components/NewsFeed';
import Footer from './components/Footer';

function App() {
  return (
    <div className="app">
      <Navbar />
      <Hero />
      <Features />
      <LivePrice />
      <NewsFeed />
      <Footer />
    </div>
  );
}

export default App;
