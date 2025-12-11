import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Trade {
  id: number;
  timestamp: string;
  message_id: string;
  ticker: string;
  strike: number;
  option_type: string;
  action: string;
  contracts: number;
  price: number | null;
  option_symbol: string;
  order_id: string;
  status: string;
  account_id: string;
  order_type: string;
}

export interface Position {
  ticker: string;
  strike: number;
  option_type: string;
  quantity: number;
  avg_entry_price: number | null;
  last_updated: string;
}

export interface Stats {
  total_trades: number;
  bought_trades: number;
  sold_trades: number;
  realized_pl: number;
}

export interface PLHistory {
  date: string;
  daily_pl: number;
  cumulative_pl: number;
}

export interface RealizedPL {
  ticker: string;
  strike: number;
  option_type: string;
  contracts: number;
  entry_price: number;
  exit_price: number;
  realized_pl: number;
}

export interface UnrealizedPL {
  ticker: string;
  strike: number;
  option_type: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pl: number;
}

export const tradesApi = {
  getAll: async (params?: {
    ticker?: string;
    action?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) => {
    const response = await api.get('/trades', { params });
    return response.data;
  },
  getById: async (id: number) => {
    const response = await api.get(`/trades/${id}`);
    return response.data;
  },
};

export const positionsApi = {
  getAll: async () => {
    const response = await api.get('/positions');
    return response.data;
  },
  getByKey: async (ticker: string, strike: number, optionType: string) => {
    const response = await api.get(`/positions/${ticker}/${strike}/${optionType}`);
    return response.data;
  },
};

export const statsApi = {
  get: async () => {
    const response = await api.get('/stats');
    return response.data;
  },
};

export const plApi = {
  getHistory: async () => {
    const response = await api.get('/pl/history');
    return response.data;
  },
  getRealized: async () => {
    const response = await api.get('/pl/realized');
    return response.data;
  },
  getUnrealized: async () => {
    const response = await api.get('/pl/unrealized');
    return response.data;
  },
};

