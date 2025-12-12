import PLSummary from './components/PLSummary';
import TradeHistory from './components/TradeHistory';
import OpenPositions from './components/OpenPositions';
import Charts from './components/Charts';
import Statistics from './components/Statistics';

function App() {
  return (
    <div className="min-h-screen bg-background">
      <header className="bg-primary text-primary-foreground py-5 px-5 text-center shadow-md">
        <h1 className="text-3xl font-bold m-0">Options Trading Bot Dashboard</h1>
      </header>
      <main className="max-w-[1400px] mx-auto p-5 flex flex-col gap-5 md:p-5">
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

