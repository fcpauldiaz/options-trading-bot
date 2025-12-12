import { useState, useEffect, useRef } from 'react';
import { format } from 'date-fns';
import { tradesApi, Trade } from '../services/api';
import { dataStreamService } from '../services/stream';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Button } from './ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Skeleton } from './ui/skeleton';

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
  const filtersRef = useRef(filters);
  const pageRef = useRef(page);
  const tradesRef = useRef(trades);

  useEffect(() => {
    filtersRef.current = filters;
    pageRef.current = page;
    tradesRef.current = trades;
  }, [filters, page, trades]);

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

  useEffect(() => {
    fetchTrades();
  }, [filters, page]);

  useEffect(() => {
    const unsubscribe = dataStreamService.subscribe((update) => {
      if (update.type === 'update' && update.data?.stats) {
        const newTotal = update.data.stats.total_trades;
        setTotal(prevTotal => {
          if (newTotal !== prevTotal) {
            const hasNoFilters = !filtersRef.current.ticker && 
                                !filtersRef.current.action && 
                                !filtersRef.current.start_date && 
                                !filtersRef.current.end_date;
            
            if (hasNoFilters && pageRef.current === 1 && tradesRef.current.length > 0) {
              fetchTrades();
            }
            return newTotal;
          }
          return prevTotal;
        });
      }
    });

    return unsubscribe;
  }, []);

  const handleFilterChange = (field: string, value: string) => {
    setFilters(prev => ({ ...prev, [field]: value }));
    setPage(1);
  };

  const totalPages = Math.ceil(total / limit);

  if (loading && trades.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Trade History</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Trade History</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Input
            type="text"
            placeholder="Ticker"
            value={filters.ticker}
            onChange={(e) => handleFilterChange('ticker', e.target.value)}
          />
          <Select value={filters.action} onValueChange={(value) => handleFilterChange('action', value)}>
            <SelectTrigger>
              <SelectValue placeholder="All Actions" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Actions</SelectItem>
              <SelectItem value="BOUGHT">Bought</SelectItem>
              <SelectItem value="SOLD">Sold</SelectItem>
            </SelectContent>
          </Select>
          <Input
            type="date"
            value={filters.start_date}
            onChange={(e) => handleFilterChange('start_date', e.target.value)}
          />
          <Input
            type="date"
            value={filters.end_date}
            onChange={(e) => handleFilterChange('end_date', e.target.value)}
          />
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Ticker</TableHead>
                <TableHead>Strike</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Contracts</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Order ID</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trades.map((trade) => (
                <TableRow key={trade.id}>
                  <TableCell>{format(new Date(trade.timestamp), 'MM/dd/yyyy HH:mm')}</TableCell>
                  <TableCell className="font-medium">{trade.ticker}</TableCell>
                  <TableCell>{trade.strike}</TableCell>
                  <TableCell>{trade.option_type}</TableCell>
                  <TableCell>
                    <span className={trade.action === 'BOUGHT' ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>
                      {trade.action}
                    </span>
                  </TableCell>
                  <TableCell>{trade.contracts}</TableCell>
                  <TableCell>${trade.price?.toFixed(2) || 'N/A'}</TableCell>
                  <TableCell>{trade.order_id}</TableCell>
                  <TableCell>{trade.status}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-4">
            <Button
              variant="outline"
              onClick={() => setPage(prev => Math.max(1, prev - 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
            <Button
              variant="outline"
              onClick={() => setPage(prev => Math.min(totalPages, prev + 1))}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default TradeHistory;

