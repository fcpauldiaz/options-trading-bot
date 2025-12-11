import React, { useState, useEffect } from 'react';
import './App.css';
import PLSummary from './components/PLSummary';
import TradeHistory from './components/TradeHistory';
import OpenPositions from './components/OpenPositions';
import Charts from './components/Charts';
import Statistics from './components/Statistics';

function App() {
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshKey(prev => prev + 1);
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>Options Trading Bot Dashboard</h1>
      </header>
      <main className="App-main">
        <PLSummary key={`pl-${refreshKey}`} />
        <Statistics key={`stats-${refreshKey}`} />
        <Charts key={`charts-${refreshKey}`} />
        <OpenPositions key={`positions-${refreshKey}`} />
        <TradeHistory key={`trades-${refreshKey}`} />
      </main>
    </div>
  );
}

export default App;

