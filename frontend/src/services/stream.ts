const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

export interface StreamUpdate {
  type: 'update' | 'error';
  data?: {
    stats?: {
      total_trades: number;
      bought_trades: number;
      sold_trades: number;
      realized_pl: number;
    };
    pl?: {
      realized: number;
      unrealized: number;
      realized_pl: Array<{
        ticker: string;
        strike: number;
        option_type: string;
        contracts: number;
        entry_price: number;
        exit_price: number;
        realized_pl: number;
      }>;
      unrealized_pl: Array<{
        ticker: string;
        strike: number;
        option_type: string;
        quantity: number;
        avg_entry_price: number;
        current_price: number;
        unrealized_pl: number;
      }>;
    };
    positions?: Array<{
      ticker: string;
      strike: number;
      option_type: string;
      quantity: number;
      avg_entry_price: number | null;
      last_updated: string;
    }>;
    pl_history?: Array<{
      date: string;
      daily_pl: number;
      cumulative_pl: number;
    }>;
    ticker_pl?: Array<{
      ticker: string;
      pl: number;
    }>;
  };
  message?: string;
}

type StreamCallback = (update: StreamUpdate) => void;

class DataStreamService {
  private eventSource: EventSource | null = null;
  private callbacks: Set<StreamCallback> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;

  connect(): void {
    if (this.eventSource?.readyState === EventSource.OPEN) {
      return;
    }

    this.disconnect();

    const url = `${API_BASE_URL}/stream`;
    this.eventSource = new EventSource(url);

    this.eventSource.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.eventSource.onmessage = (event) => {
      try {
        const update: StreamUpdate = JSON.parse(event.data);
        this.callbacks.forEach(callback => callback(update));
      } catch (error) {
        console.error('Error parsing stream message:', error);
      }
    };

    this.eventSource.onerror = (error) => {
      console.error('Stream error:', error);
      this.eventSource?.close();
      
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        setTimeout(() => {
          this.connect();
        }, this.reconnectDelay * this.reconnectAttempts);
      }
    };
  }

  subscribe(callback: StreamCallback): () => void {
    this.callbacks.add(callback);
    
    if (!this.eventSource || this.eventSource.readyState === EventSource.CLOSED) {
      this.connect();
    }
    
    return () => {
      this.callbacks.delete(callback);
      if (this.callbacks.size === 0) {
        this.disconnect();
      }
    };
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}

export const dataStreamService = new DataStreamService();
