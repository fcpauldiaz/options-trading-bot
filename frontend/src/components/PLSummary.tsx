import { useState, useEffect } from 'react';
import { plApi } from '../services/api';
import { dataStreamService } from '../services/stream';
import './PLSummary.css';

const PLSummary: React.FC = () => {
  const [realizedPL, setRealizedPL] = useState<number>(0);
  const [unrealizedPL, setUnrealizedPL] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPL = async () => {
      try {
        const [realizedData, unrealizedData] = await Promise.all([
          plApi.getRealized(),
          plApi.getUnrealized(),
        ]);

        const totalRealized = realizedData.realized_pl?.reduce(
          (sum: number, item: any) => sum + (item.realized_pl || 0),
          0
        ) || 0;

        const totalUnrealized = unrealizedData.unrealized_pl?.reduce(
          (sum: number, item: any) => sum + (item.unrealized_pl || 0),
          0
        ) || 0;

        setRealizedPL(totalRealized);
        setUnrealizedPL(totalUnrealized);
      } catch (error) {
        console.error('Error fetching P/L data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPL();

    const unsubscribe = dataStreamService.subscribe((update) => {
      if (update.type === 'update' && update.data?.pl) {
        setRealizedPL(update.data.pl.realized || 0);
        setUnrealizedPL(update.data.pl.unrealized || 0);
      }
    });

    return unsubscribe;
  }, []);

  const netPL = realizedPL + unrealizedPL;

  if (loading) {
    return <div className="pl-summary loading">Loading P/L data...</div>;
  }

  return (
    <div className="pl-summary">
      <h2>Profit & Loss Summary</h2>
      <div className="pl-cards">
        <div className="pl-card">
          <div className="pl-label">Realized P/L</div>
          <div className={`pl-value ${realizedPL >= 0 ? 'positive' : 'negative'}`}>
            ${realizedPL.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="pl-card">
          <div className="pl-label">Unrealized P/L</div>
          <div className={`pl-value ${unrealizedPL >= 0 ? 'positive' : 'negative'}`}>
            ${unrealizedPL.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div className="pl-card net">
          <div className="pl-label">Net P/L</div>
          <div className={`pl-value ${netPL >= 0 ? 'positive' : 'negative'}`}>
            ${netPL.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PLSummary;

