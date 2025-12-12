import { useState, useEffect, useRef } from 'react';
import { statsApi, plApi } from '../services/api';
import { dataStreamService } from '../services/stream';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Skeleton } from './ui/skeleton';

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
        setStats({
          total_trades: 0,
          bought_trades: 0,
          sold_trades: 0,
          realized_pl: 0
        });
        setWinRate(0);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();

    let unsubscribe: (() => void) | undefined;
    try {
      unsubscribe = dataStreamService.subscribe((update) => {
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
    } catch (error) {
      console.error('Error subscribing to stream:', error);
    }

    return () => {
      if (unsubscribe) {
        unsubscribe();
      }
    };
  }, []);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const avgProfitPerTrade = stats.realized_pl && stats.sold_trades > 0
    ? stats.realized_pl / stats.sold_trades
    : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Statistics</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-2">Total Trades</div>
              <div className="text-2xl font-bold">{stats.total_trades}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-2">Bought</div>
              <div className="text-2xl font-bold">{stats.bought_trades}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-2">Sold</div>
              <div className="text-2xl font-bold">{stats.sold_trades}</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-2">Win Rate</div>
              <div className="text-2xl font-bold">{winRate.toFixed(1)}%</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-2">Avg Profit/Trade</div>
              <div className={`text-2xl font-bold ${avgProfitPerTrade >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${avgProfitPerTrade.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-2">Total Realized P/L</div>
              <div className={`text-2xl font-bold ${stats.realized_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${(stats.realized_pl || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </CardContent>
          </Card>
        </div>
      </CardContent>
    </Card>
  );
};

export default Statistics;

