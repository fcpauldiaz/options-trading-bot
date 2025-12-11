import { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { plApi } from '../services/api';
import './Charts.css';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

const Charts: React.FC = () => {
  const [plHistory, setPLHistory] = useState<any[]>([]);
  const [realizedPL, setRealizedPL] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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
      } finally {
        setLoading(false);
      }
    };

    fetchChartData();
  }, []);

  if (loading) {
    return <div className="charts loading">Loading charts...</div>;
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
    <div className="charts">
      <h2>Charts</h2>
      <div className="charts-grid">
        <div className="chart-container">
          <h3>Cumulative P/L Over Time</h3>
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
        </div>

        <div className="chart-container">
          <h3>P/L by Ticker</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={realizedPL}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="ticker" />
              <YAxis />
              <Tooltip formatter={(value: any) => `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
              <Bar dataKey="pl" fill="#8884d8" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-container">
          <h3>Win/Loss Distribution</h3>
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
        </div>
      </div>
    </div>
  );
};

export default Charts;

