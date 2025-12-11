import { useState, useEffect, useRef } from 'react';
import { statsApi, plApi } from '../services/api';
import { dataStreamService } from '../services/stream';
import './Statistics.css';

const Statistics: React.FC = () => {
  const [stats, setStats] = useState<any>(null);
  const [winRate, setWinRate] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const fetchInitiatedRef = useRef(false);

  useEffect(() => {
    if (fetchInitiatedRef.current) return;
    fetchInitiatedRef.current = true;

    const fetchStats = async () => {
      try {
        const [statsData, realizedData] = await Promise.all([
          statsApi.get(),
          plApi.getRealized(),
        ]);

        setStats(statsData);

        const profitableTrades = realizedData.realized_pl?.filter(
          (item: any) => item.realized_pl > 0
        ).length || 0;

        const totalClosedTrades = realizedData.realized_pl?.length || 0;
        const calculatedWinRate = totalClosedTrades > 0
          ? (profitableTrades / totalClosedTrades) * 100
          : 0;

        setWinRate(calculatedWinRate);
      } catch (error) {
        console.error('Error fetching statistics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();

    const unsubscribe = dataStreamService.subscribe((update) => {
      if (update.type === 'update' && update.data) {
        if (update.data.stats) {
          setStats(update.data.stats);
        }
        if (update.data.pl?.realized_pl) {
          const profitableTrades = update.data.pl.realized_pl.filter(
            (item: any) => item.realized_pl > 0
          ).length;
          const totalClosedTrades = update.data.pl.realized_pl.length;
          const calculatedWinRate = totalClosedTrades > 0
            ? (profitableTrades / totalClosedTrades) * 100
            : 0;
          setWinRate(calculatedWinRate);
        }
      }
    });

    return unsubscribe;
  }, []);

  if (loading || !stats) {
    return <div className="statistics loading">Loading statistics...</div>;
  }

  const avgProfitPerTrade = stats.realized_pl && stats.sold_trades > 0
    ? stats.realized_pl / stats.sold_trades
    : 0;

  return (
    <div className="statistics">
      <h2>Statistics</h2>
      <div className="stats-grid">
        <div className="stat-item">
          <div className="stat-label">Total Trades</div>
          <div className="stat-value">{stats.total_trades}</div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Bought</div>
          <div className="stat-value">{stats.bought_trades}</div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Sold</div>
          <div className="stat-value">{stats.sold_trades}</div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Win Rate</div>
          <div className="stat-value">{winRate.toFixed(1)}%</div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Avg Profit/Trade</div>
          <div className={`stat-value ${avgProfitPerTrade >= 0 ? 'positive' : 'negative'}`}>
            ${avgProfitPerTrade.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="stat-item">
          <div className="stat-label">Total Realized P/L</div>
          <div className={`stat-value ${stats.realized_pl >= 0 ? 'positive' : 'negative'}`}>
            ${(stats.realized_pl || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Statistics;

