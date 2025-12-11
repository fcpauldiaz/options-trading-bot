import { useState, useEffect } from 'react';
import { positionsApi, plApi } from '../services/api';
import { dataStreamService } from '../services/stream';
import './OpenPositions.css';

const OpenPositions: React.FC = () => {
  const [positions, setPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const [positionsData, unrealizedData] = await Promise.all([
          positionsApi.getAll(),
          plApi.getUnrealized(),
        ]);

        const plMap = new Map();
        (unrealizedData.unrealized_pl || []).forEach((item: any) => {
          const key = `${item.ticker}-${item.strike}-${item.option_type}`;
          plMap.set(key, item);
        });

        const positionsWithPL = (positionsData.positions || []).map((pos: any) => {
          const key = `${pos.ticker}-${pos.strike}-${pos.option_type}`;
          const plData = plMap.get(key);
          return {
            ...pos,
            current_price: plData?.current_price || null,
            unrealized_pl: plData?.unrealized_pl || 0,
          };
        });

        setPositions(positionsWithPL);
      } catch (error) {
        console.error('Error fetching positions:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPositions();

    const unsubscribe = dataStreamService.subscribe((update) => {
      if (update.type === 'update' && update.data) {
        if (update.data.positions && update.data.pl?.unrealized_pl) {
          const plMap = new Map();
          update.data.pl.unrealized_pl.forEach((item: any) => {
            const key = `${item.ticker}-${item.strike}-${item.option_type}`;
            plMap.set(key, item);
          });

          const positionsWithPL = update.data.positions.map((pos: any) => {
            const key = `${pos.ticker}-${pos.strike}-${pos.option_type}`;
            const plData = plMap.get(key);
            return {
              ...pos,
              current_price: plData?.current_price || null,
              unrealized_pl: plData?.unrealized_pl || 0,
            };
          });

          setPositions(positionsWithPL);
        }
      }
    });

    return unsubscribe;
  }, []);

  if (loading) {
    return <div className="open-positions loading">Loading positions...</div>;
  }

  if (positions.length === 0) {
    return (
      <div className="open-positions">
        <h2>Open Positions</h2>
        <p>No open positions</p>
      </div>
    );
  }

  return (
    <div className="open-positions">
      <h2>Open Positions</h2>
      <div className="positions-table-container">
        <table className="positions-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Strike</th>
              <th>Type</th>
              <th>Quantity</th>
              <th>Avg Entry</th>
              <th>Current Price</th>
              <th>Unrealized P/L</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((pos, index) => (
              <tr key={index}>
                <td>{pos.ticker}</td>
                <td>{pos.strike}</td>
                <td>{pos.option_type}</td>
                <td>{pos.quantity}</td>
                <td>${pos.avg_entry_price?.toFixed(2) || 'N/A'}</td>
                <td>${pos.current_price?.toFixed(2) || 'N/A'}</td>
                <td className={pos.unrealized_pl >= 0 ? 'positive' : 'negative'}>
                  ${pos.unrealized_pl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default OpenPositions;

