'use client';

import React, { createContext, useContext, useState, useEffect, useRef, useCallback, ReactNode } from 'react';
import { fetchTickers, fetchCompanyName } from './api';
import { getCompanyName } from './company-names';

interface TickerContextType {
  ticker: string;
  setTicker: (t: string) => void;
  tickers: string[];
  companyName: string | null;
  validating: boolean;
  invalidTicker: string | null;
}

const TickerContext = createContext<TickerContextType>({
  ticker: 'AAPL',
  setTicker: () => {},
  tickers: [],
  companyName: 'Apple Inc.',
  validating: false,
  invalidTicker: null,
});

export function TickerProvider({ children }: { children: ReactNode }) {
  const [ticker, setTicker] = useState('AAPL');
  const [tickers, setTickers] = useState<string[]>(['AAPL', 'GOOGL', 'JPM', 'MSFT', 'TSLA']);
  const [companyName, setCompanyName] = useState<string | null>('Apple Inc.');
  const [validating, setValidating] = useState(false);
  const [invalidTicker, setInvalidTicker] = useState<string | null>(null);
  const nameCache = useRef<Record<string, string | null>>({});
  const invalidTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    fetchTickers()
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setTickers(data);
        }
      })
      .catch(() => {});
  }, []);

  // Resolve company name whenever ticker changes (only for already-accepted tickers)
  useEffect(() => {
    const staticName = getCompanyName(ticker);
    if (staticName) {
      setCompanyName(staticName);
      nameCache.current[ticker] = staticName;
      return;
    }
    if (ticker in nameCache.current) {
      setCompanyName(nameCache.current[ticker]);
      return;
    }
    // For validated custom tickers where the name wasn't cached yet
    setCompanyName(null);
    fetchCompanyName(ticker)
      .then((res) => {
        nameCache.current[ticker] = res.name;
        setCompanyName(res.name);
      })
      .catch(() => {
        nameCache.current[ticker] = null;
        setCompanyName(null);
      });
  }, [ticker]);

  const handleSetTicker = useCallback((t: string) => {
    const clean = t.replace(/[^A-Z0-9.]/gi, '').toUpperCase();
    if (!clean) return;

    // Clear any previous invalid ticker message
    setInvalidTicker(null);
    if (invalidTimerRef.current) clearTimeout(invalidTimerRef.current);

    // 1. Already in tickers list (pre-loaded or previously validated) — accept immediately
    if (tickers.includes(clean)) {
      setTicker(clean);
      return;
    }

    // 2. In static company names map — accept immediately
    if (getCompanyName(clean)) {
      setTicker(clean);
      setTickers((prev) => (prev.includes(clean) ? prev : [...prev, clean]));
      return;
    }

    // 3. Unknown ticker — validate via API before accepting
    setValidating(true);
    fetchCompanyName(clean)
      .then((res) => {
        if (res.valid) {
          nameCache.current[clean] = res.name;
          setTicker(clean);
          setTickers((prev) => (prev.includes(clean) ? prev : [...prev, clean]));
        } else {
          setInvalidTicker(clean);
          invalidTimerRef.current = setTimeout(() => setInvalidTicker(null), 3000);
        }
      })
      .catch(() => {
        setInvalidTicker(clean);
        invalidTimerRef.current = setTimeout(() => setInvalidTicker(null), 3000);
      })
      .finally(() => setValidating(false));
  }, [tickers]);

  return (
    <TickerContext.Provider value={{ ticker, setTicker: handleSetTicker, tickers, companyName, validating, invalidTicker }}>
      {children}
    </TickerContext.Provider>
  );
}

export function useTicker() {
  return useContext(TickerContext);
}
