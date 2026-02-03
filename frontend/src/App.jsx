import Hero from './components/Hero';
import Features from './components/Features';
import LivePrice from './components/LivePrice';
import NewsFeed from './components/NewsFeed';
import Footer from './components/Footer';

function App() {
  return (
    <div className="app">
      <Hero />
      <Features />
      <LivePrice />
      <NewsFeed />
      <Footer />
    </div>
  );
}

export default App;
