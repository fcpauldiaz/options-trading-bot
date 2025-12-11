import './App.css';
import PLSummary from './components/PLSummary';
import TradeHistory from './components/TradeHistory';
import OpenPositions from './components/OpenPositions';
import Charts from './components/Charts';
import Statistics from './components/Statistics';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Options Trading Bot Dashboard</h1>
      </header>
      <main className="App-main">
        <PLSummary />
        <Statistics />
        <Charts />
        <OpenPositions />
        <TradeHistory />
      </main>
    </div>
  );
}

export default App;

