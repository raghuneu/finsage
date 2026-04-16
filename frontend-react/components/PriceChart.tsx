'use client';

import React, { useEffect, useRef, useMemo } from 'react';
import { Box, Typography } from '@mui/material';
import { createChart, ColorType, LineSeries, HistogramSeries } from 'lightweight-charts';
import type { IChartApi } from 'lightweight-charts';

interface PriceData {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  sma_7d?: number | null;
  sma_30d?: number | null;
  sma_90d?: number | null;
}

interface PriceChartProps {
  data: PriceData[];
  height?: number;
  showVolume?: boolean;
  showSMA?: boolean;
  title?: string;
}

export default function PriceChart({
  data,
  height = 450,
  showVolume = true,
  showSMA = true,
  title,
}: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const sortedData = useMemo(
    () => [...data].sort((a, b) => a.date.localeCompare(b.date)),
    [data]
  );

  useEffect(() => {
    if (!chartContainerRef.current || sortedData.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(chartContainerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#6B6760',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#E8E4DB40' },
        horzLines: { color: '#E8E4DB40' },
      },
      rightPriceScale: {
        borderColor: '#E8E4DB',
      },
      timeScale: {
        borderColor: '#E8E4DB',
        timeVisible: false,
      },
    });

    chartRef.current = chart;

    // Main price line — Star Command Blue
    const priceSeries = chart.addSeries(LineSeries, {
      color: '#0382B7',
      lineWidth: 2,
      priceFormat: { type: 'price' as const, precision: 2, minMove: 0.01 },
    });
    priceSeries.setData(
      sortedData
        .filter((d) => d.close != null)
        .map((d) => ({ time: d.date, value: d.close! }))
    );

    // SMA lines — palette rotation
    if (showSMA) {
      const smaConfigs: { key: keyof PriceData; color: string }[] = [
        { key: 'sma_7d', color: '#9DCBB8' },   // Turquoise Green
        { key: 'sma_30d', color: '#F8CB86' },   // Topaz
        { key: 'sma_90d', color: '#E58B6D' },   // Middle Red
      ];
      for (const { key, color } of smaConfigs) {
        const filtered = sortedData.filter((d) => d[key] != null);
        if (filtered.length > 0) {
          const s = chart.addSeries(LineSeries, {
            color,
            lineWidth: 1,
          });
          s.setData(filtered.map((d) => ({ time: d.date, value: d[key] as number })));
        }
      }
    }

    // Volume histogram — bullish/bearish from palette
    if (showVolume) {
      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' as const },
        priceScaleId: 'volume',
      });
      chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(
        sortedData
          .filter((d) => d.volume != null)
          .map((d) => ({
            time: d.date,
            value: d.volume!,
            color:
              d.close != null && d.open != null && d.close >= d.open
                ? '#9DCBB860'  // Turquoise Green (bullish)
                : '#E58B6D60', // Middle Red (bearish)
          }))
      );
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [sortedData, height, showVolume, showSMA]);

  return (
    <Box>
      {title && (
        <Typography variant="body2" sx={{ color: '#6B6760', mb: 1, fontSize: '0.8rem' }}>
          {title}
        </Typography>
      )}
      <div ref={chartContainerRef} style={{ width: '100%' }} />
      {showSMA && (
        <Box sx={{ display: 'flex', gap: 2, mt: 1, flexWrap: 'wrap' }}>
          {[
            { label: 'Close', color: '#0382B7' },
            { label: 'SMA 7D', color: '#9DCBB8' },
            { label: 'SMA 30D', color: '#F8CB86' },
            { label: 'SMA 90D', color: '#E58B6D' },
          ].map((item) => (
            <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box
                sx={{
                  width: 12,
                  height: 2,
                  backgroundColor: item.color,
                  borderRadius: 1,
                }}
              />
              <Typography variant="caption" sx={{ fontSize: '0.7rem', color: '#6B6760' }}>
                {item.label}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
