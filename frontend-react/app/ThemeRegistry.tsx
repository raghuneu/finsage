'use client';

import React from 'react';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v16-appRouter';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import theme from '@/lib/theme';
import { TickerProvider } from '@/lib/ticker-context';
import AppShell from '@/components/AppShell';

export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  return (
    <AppRouterCacheProvider options={{ enableCssLayer: true }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <TickerProvider>
          <AppShell>{children}</AppShell>
        </TickerProvider>
      </ThemeProvider>
    </AppRouterCacheProvider>
  );
}
