import { useState, useEffect, useRef } from 'react';
import { positionsApi, plApi } from '../services/api';
import { dataStreamService } from '../services/stream';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Skeleton } from './ui/skeleton';

const OpenPositions: React.FC = () => {
  const [positions, setPositions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const hasFetchedRef = useRef(false);

  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;

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
        setPositions([]);
      } finally {
        setLoading(false);
      }
    };

    fetchPositions();

    let unsubscribe: (() => void) | undefined;
    try {
      unsubscribe = dataStreamService.subscribe((update) => {
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
          <CardTitle>Open Positions</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (positions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Open Positions</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">No open positions</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Open Positions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ticker</TableHead>
                <TableHead>Strike</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Quantity</TableHead>
                <TableHead>Avg Entry</TableHead>
                <TableHead>Current Price</TableHead>
                <TableHead>Unrealized P/L</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {positions.map((pos, index) => (
                <TableRow key={index}>
                  <TableCell className="font-medium">{pos.ticker}</TableCell>
                  <TableCell>{pos.strike}</TableCell>
                  <TableCell>{pos.option_type}</TableCell>
                  <TableCell>{pos.quantity}</TableCell>
                  <TableCell>${pos.avg_entry_price?.toFixed(2) || 'N/A'}</TableCell>
                  <TableCell>${pos.current_price?.toFixed(2) || 'N/A'}</TableCell>
                  <TableCell className={pos.unrealized_pl >= 0 ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>
                    ${pos.unrealized_pl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
};

export default OpenPositions;

