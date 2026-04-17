'use client';

import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Divider,
  List,
  ListItem,
  ListItemText,
  Alert,
} from '@mui/material';
import CircleIcon from '@mui/icons-material/Circle';
import { useTicker } from '@/lib/ticker-context';
import { fetchKPIs, fetchPriceHistory, fetchHeadlines } from '@/lib/api';
import MetricCard from '@/components/MetricCard';
import SignalBadge from '@/components/SignalBadge';
import SectionHeader from '@/components/SectionHeader';
import PriceChart from '@/components/PriceChart';
import { DashboardSkeleton } from '@/components/LoadingSkeleton';

function fmtMoney(val: number | null | undefined): string {
  if (val == null) return 'N/A';
  const abs = Math.abs(val);
  if (abs >= 1e12) return `$${(val / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(val / 1e6).toFixed(1)}M`;
  return `$${val.toLocaleString()}`;
}

export default function DashboardPage() {
  const { ticker } = useTicker();
  const [kpis, setKpis] = useState<Record<string, unknown> | null>(null);
  const [priceData, setPriceData] = useState<unknown[]>([]);
  const [headlines, setHeadlines] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchKPIs(ticker),
      fetchPriceHistory(ticker, 90),
      fetchHeadlines(ticker, 10),
    ])
      .then(([k, p, h]) => {
        setKpis(k);
        setPriceData(p);
        setHeadlines(h);
      })
      .catch((e) => setError(e.message || 'Failed to load dashboard data'))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) return <DashboardSkeleton />;
  if (error) return <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>;
  if (!kpis) return null;

  const profile = (kpis.profile || {}) as Record<string, unknown>;
  const stock = (kpis.stock || {}) as Record<string, unknown>;
  const fundamentals = (kpis.fundamentals || {}) as Record<string, unknown>;
  const sentiment = (kpis.sentiment || {}) as Record<string, unknown>;
  const secFin = (kpis.sec_financials || {}) as Record<string, unknown>;

  const signals = [
    { label: 'Stock Trend', signal: stock.trend_signal as string },
    { label: 'Fundamentals', signal: fundamentals.fundamental_signal as string },
    { label: 'Sentiment', signal: sentiment.sentiment_label as string },
    { label: 'Financial Health', signal: secFin.financial_health as string },
  ];

  return (
    <Box>
      {/* KPI Cards */}
      <SectionHeader title="Key Metrics" subtitle="Latest data from the analytics layer" />
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 6, md: 2.4 }}>
          <MetricCard title="Market Cap" value={fmtMoney(profile.market_cap as number)} />
        </Grid>
        <Grid size={{ xs: 6, md: 2.4 }}>
          <MetricCard
            title="Price"
            value={stock.close != null ? `$${Number(stock.close).toFixed(2)}` : 'N/A'}
            delta={
              stock.daily_return_pct != null
                ? `${Number(stock.daily_return_pct) >= 0 ? '+' : ''}${Number(stock.daily_return_pct).toFixed(2)}%`
                : undefined
            }
          />
        </Grid>
        <Grid size={{ xs: 6, md: 2.4 }}>
          <MetricCard
            title="Revenue"
            value={fmtMoney(fundamentals.revenue as number)}
            delta={
              fundamentals.revenue_growth_yoy_pct != null
                ? `${Number(fundamentals.revenue_growth_yoy_pct) >= 0 ? '+' : ''}${Number(fundamentals.revenue_growth_yoy_pct).toFixed(1)}% YoY`
                : undefined
            }
          />
        </Grid>
        <Grid size={{ xs: 6, md: 2.4 }}>
          <MetricCard
            title="Sentiment"
            value={sentiment.sentiment_score != null ? Number(sentiment.sentiment_score).toFixed(3) : 'N/A'}
            delta={sentiment.sentiment_trend as string}
          />
        </Grid>
        <Grid size={{ xs: 6, md: 2.4 }}>
          <MetricCard
            title="P/E Ratio"
            value={profile.pe_ratio != null ? Number(profile.pe_ratio).toFixed(1) : 'N/A'}
          />
        </Grid>
      </Grid>

      {/* Signal Strip — unified card with all 4 signals */}
      <SectionHeader title="Market Signals" />
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ p: 0, '&:last-child': { pb: 0 } }}>
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
            }}
          >
            {signals.map((item, i) => (
              <Box
                key={item.label}
                sx={{
                  flex: '1 1 25%',
                  minWidth: 140,
                  textAlign: 'center',
                  py: 2,
                  px: 1.5,
                  borderRight: i < signals.length - 1 ? '1px solid' : 'none',
                  borderColor: 'divider',
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    color: '#6B6760',
                    fontSize: '0.6rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    fontWeight: 600,
                  }}
                >
                  {item.label}
                </Typography>
                <Box sx={{ mt: 1 }}>
                  <SignalBadge label={item.signal || 'N/A'} signal={item.signal} />
                </Box>
              </Box>
            ))}
          </Box>
        </CardContent>
      </Card>

      <Divider sx={{ mb: 3 }} />

      {/* Price Chart */}
      <SectionHeader title="Price History" subtitle="Last 90 trading days with moving averages" />
      <Card sx={{ mb: 3, p: 2 }}>
        {(priceData as unknown[]).length > 0 ? (
          <PriceChart data={priceData as never[]} height={450} />
        ) : (
          <Typography variant="body2" sx={{ textAlign: 'center', py: 4, color: '#6B6760' }}>
            No price history available for this ticker.
          </Typography>
        )}
      </Card>

      <Divider sx={{ mb: 3 }} />

      {/* Headlines */}
      <SectionHeader title="Recent Headlines" subtitle="Latest news articles from the data pipeline" />
      <Card>
        {(headlines as unknown[]).length > 0 ? (
          <List disablePadding>
            {(headlines as Array<{ title: string; published_at: string; source_name: string }>).map(
              (h, i) => (
                <ListItem
                  key={i}
                  divider={i < headlines.length - 1}
                  sx={{
                    borderColor: '#E8E4DB',
                    py: 1.5,
                    px: 2.5,
                    transition: 'background-color 0.2s ease',
                    '&:hover': {
                      backgroundColor: 'rgba(201, 107, 174, 0.04)',
                    },
                  }}
                >
                  <Box
                    sx={{
                      width: 3,
                      alignSelf: 'stretch',
                      backgroundColor: '#C96BAE',
                      borderRadius: 1,
                      mr: 2,
                      flexShrink: 0,
                    }}
                  />
                  <ListItemText
                    primary={h.title}
                    secondary={
                      <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                        <Typography component="span" sx={{ fontSize: '0.7rem', color: '#9A9590' }}>
                          {(h.published_at || '').slice(0, 10)}
                        </Typography>
                        {h.source_name && (
                          <>
                            <CircleIcon sx={{ fontSize: 4, color: '#D4CFC9' }} />
                            <Typography component="span" sx={{ fontSize: '0.7rem', color: '#B0AAA3', fontStyle: 'italic' }}>
                              {h.source_name}
                            </Typography>
                          </>
                        )}
                      </Box>
                    }
                    slotProps={{
                      primary: {
                        sx: {
                          fontSize: '0.85rem',
                          fontWeight: 500,
                          color: '#2C2A25',
                          lineHeight: 1.5,
                        },
                      },
                    }}
                  />
                </ListItem>
              )
            )}
          </List>
        ) : (
          <CardContent>
            <Typography variant="body2" sx={{ textAlign: 'center', color: '#6B6760' }}>
              No recent headlines available.
            </Typography>
          </CardContent>
        )}
      </Card>
    </Box>
  );
}
