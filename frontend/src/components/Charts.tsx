import { useState, useEffect, useRef } from 'react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { plApi } from '../services/api';
import { dataStreamService } from '../services/stream';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Skeleton } from './ui/skeleton';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

const Charts: React.FC = () => {
  const [plHistory, setPLHistory] = useState<any[]>([]);
  const [realizedPL, setRealizedPL] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const hasFetchedRef = useRef(false);

  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;

    const fetchChartData = async () => {
      try {
        const [historyData, realizedData] = await Promise.all([
          plApi.getHistory(),
          plApi.getRealized(),
        ]);

        setPLHistory(historyData.history || []);
        
        const tickerPL = (realizedData.realized_pl || []).reduce((acc: any, item: any) => {
          const key = item.ticker;
          if (!acc[key]) {
            acc[key] = 0;
          }
          acc[key] += item.realized_pl || 0;
          return acc;
        }, {});

        const tickerData = Object.entries(tickerPL).map(([ticker, pl]) => ({
          ticker,
          pl: pl as number,
        }));

        setRealizedPL(tickerData);
      } catch (error) {
        console.error('Error fetching chart data:', error);
        setPLHistory([]);
        setRealizedPL([]);
      } finally {
        setLoading(false);
      }
    };

    fetchChartData();

    let unsubscribe: (() => void) | undefined;
    try {
      unsubscribe = dataStreamService.subscribe((update) => {
      if (update.type === 'update' && update.data) {
        if (update.data.pl_history) {
          setPLHistory(update.data.pl_history);
        }
        if (update.data.ticker_pl) {
          setRealizedPL(update.data.ticker_pl);
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
          <CardTitle>Charts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Skeleton className="h-[300px]" />
            <Skeleton className="h-[300px]" />
            <Skeleton className="h-[300px]" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const winLossData = realizedPL.reduce((acc, item) => {
    if (item.pl > 0) {
      acc.wins += item.pl;
    } else {
      acc.losses += Math.abs(item.pl);
    }
    return acc;
  }, { wins: 0, losses: 0 });

  const pieData = [
    { name: 'Wins', value: winLossData.wins },
    { name: 'Losses', value: winLossData.losses },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Charts</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Cumulative P/L Over Time</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={plHistory}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip formatter={(value: any) => `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                  <Legend />
                  <Line type="monotone" dataKey="cumulative_pl" stroke="#8884d8" name="Cumulative P/L" />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">P/L by Ticker</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={realizedPL}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="ticker" />
                  <YAxis />
                  <Tooltip formatter={(value: any) => `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                  <Bar dataKey="pl" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Win/Loss Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {pieData.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: any) => `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      </CardContent>
    </Card>
  );
};

export default Charts;

