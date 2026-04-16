'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { fetchTickers } from './api';

interface TickerContextType {
  ticker: string;
  setTicker: (t: string) => void;
  tickers: string[];
}

const TickerContext = createContext<TickerContextType>({
  ticker: 'AAPL',
  setTicker: () => {},
  tickers: [],
});

export function TickerProvider({ children }: { children: ReactNode }) {
  const [ticker, setTicker] = useState('AAPL');
  const [tickers, setTickers] = useState<string[]>(['AAPL', 'GOOGL', 'JPM', 'MSFT', 'TSLA']);

  useEffect(() => {
    fetchTickers()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setTickers(data);
        }
      })
      .catch(() => {});
  }, []);

  const handleSetTicker = (t: string) => {
    const clean = t.replace(/[^A-Z0-9.]/gi, '').toUpperCase();
    if (!clean) return;
    setTicker(clean);
    // Add to suggestions list if not already present
    setTickers((prev) => (prev.includes(clean) ? prev : [...prev, clean]));
  };

  return (
    <TickerContext.Provider value={{ ticker, setTicker: handleSetTicker, tickers }}>
      {children}
    </TickerContext.Provider>
  );
}

export function useTicker() {
  return useContext(TickerContext);
}
