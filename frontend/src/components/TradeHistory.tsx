import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { tradesApi, Trade } from '../services/api';
import './TradeHistory.css';

const TradeHistory: React.FC = () => {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    ticker: '',
    action: '',
    start_date: '',
    end_date: '',
  });
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 50;

  useEffect(() => {
    fetchTrades();
  }, [filters, page]);

  const fetchTrades = async () => {
    try {
      setLoading(true);
      const params: any = {
        limit,
        offset: (page - 1) * limit,
      };

      if (filters.ticker) params.ticker = filters.ticker;
      if (filters.action) params.action = filters.action;
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;

      const data = await tradesApi.getAll(params);
      setTrades(data.trades || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error('Error fetching trades:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (field: string, value: string) => {
    setFilters(prev => ({ ...prev, [field]: value }));
    setPage(1);
  };

  const totalPages = Math.ceil(total / limit);

  if (loading && trades.length === 0) {
    return <div className="trade-history loading">Loading trades...</div>;
  }

  return (
    <div className="trade-history">
      <h2>Trade History</h2>
      
      <div className="filters">
        <input
          type="text"
          placeholder="Ticker"
          value={filters.ticker}
          onChange={(e) => handleFilterChange('ticker', e.target.value)}
          className="filter-input"
        />
        <select
          value={filters.action}
          onChange={(e) => handleFilterChange('action', e.target.value)}
          className="filter-select"
        >
          <option value="">All Actions</option>
          <option value="BOUGHT">Bought</option>
          <option value="SOLD">Sold</option>
        </select>
        <input
          type="date"
          value={filters.start_date}
          onChange={(e) => handleFilterChange('start_date', e.target.value)}
          className="filter-input"
        />
        <input
          type="date"
          value={filters.end_date}
          onChange={(e) => handleFilterChange('end_date', e.target.value)}
          className="filter-input"
        />
      </div>

      <div className="trades-table-container">
        <table className="trades-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Ticker</th>
              <th>Strike</th>
              <th>Type</th>
              <th>Action</th>
              <th>Contracts</th>
              <th>Price</th>
              <th>Order ID</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade) => (
              <tr key={trade.id}>
                <td>{format(new Date(trade.timestamp), 'MM/dd/yyyy HH:mm')}</td>
                <td>{trade.ticker}</td>
                <td>{trade.strike}</td>
                <td>{trade.option_type}</td>
                <td className={trade.action === 'BOUGHT' ? 'action-bought' : 'action-sold'}>
                  {trade.action}
                </td>
                <td>{trade.contracts}</td>
                <td>${trade.price?.toFixed(2) || 'N/A'}</td>
                <td>{trade.order_id}</td>
                <td>{trade.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="pagination">
          <button
            onClick={() => setPage(prev => Math.max(1, prev - 1))}
            disabled={page === 1}
          >
            Previous
          </button>
          <span>Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage(prev => Math.min(totalPages, prev + 1))}
            disabled={page === totalPages}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default TradeHistory;

