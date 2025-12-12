import { useState, useEffect, useRef } from 'react';
import { plApi } from '../services/api';
import { dataStreamService } from '../services/stream';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Skeleton } from './ui/skeleton';

const PLSummary: React.FC = () => {
  const [realizedPL, setRealizedPL] = useState<number>(0);
  const [unrealizedPL, setUnrealizedPL] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const hasFetchedRef = useRef(false);

  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;

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
    return (
      <Card>
        <CardHeader>
          <CardTitle>Profit & Loss Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profit & Loss Summary</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-2">Realized P/L</div>
              <div className={`text-2xl font-bold ${realizedPL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${realizedPL.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-2">Unrealized P/L</div>
              <div className={`text-2xl font-bold ${unrealizedPL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${unrealizedPL.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </CardContent>
          </Card>
          <Card className="border-2 border-primary">
            <CardContent className="pt-6">
              <div className="text-sm font-medium text-muted-foreground mb-2">Net P/L</div>
              <div className={`text-2xl font-bold ${netPL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${netPL.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </CardContent>
          </Card>
        </div>
      </CardContent>
    </Card>
  );
};

export default PLSummary;

