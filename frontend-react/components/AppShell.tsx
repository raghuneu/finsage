'use client';

import React, { useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  Typography,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Autocomplete,
  TextField,
  Divider,
  IconButton,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import BarChartIcon from '@mui/icons-material/BarChart';
import DescriptionIcon from '@mui/icons-material/Description';
import ArticleIcon from '@mui/icons-material/Article';
import ChatIcon from '@mui/icons-material/Chat';
import MenuIcon from '@mui/icons-material/Menu';
import { useTicker } from '@/lib/ticker-context';

const DRAWER_WIDTH = 220;

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/', icon: <DashboardIcon /> },
  { label: 'Analytics', path: '/analytics', icon: <BarChartIcon /> },
  { label: 'SEC Filings', path: '/sec', icon: <DescriptionIcon /> },
  { label: 'Report', path: '/report', icon: <ArticleIcon /> },
  { label: 'Ask FinSage', path: '/ask', icon: <ChatIcon /> },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { ticker, setTicker, tickers } = useTicker();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);

  const currentPage = NAV_ITEMS.find(
    (item) => pathname === item.path || (item.path !== '/' && pathname.startsWith(item.path))
  );

  const drawerContent = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Logo */}
      <Box sx={{ px: 2.5, pt: 2.5, pb: 2 }}>
        <Typography
          sx={{
            fontFamily: '"DM Serif Display", Georgia, serif',
            fontSize: '1.4rem',
            color: '#2C2A25',
            lineHeight: 1,
          }}
        >
          FinSage
        </Typography>
        <Box
          sx={{
            mt: 0.75,
            width: 28,
            height: 2,
            borderRadius: 1,
            background: 'linear-gradient(90deg, #C96BAE 0%, transparent 100%)',
          }}
        />
        <Typography
          variant="caption"
          sx={{
            color: '#9A9590',
            fontSize: '0.55rem',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            mt: 0.5,
            display: 'block',
          }}
        >
          AI Financial Research
        </Typography>
      </Box>

      <Divider />

      {/* Ticker selector */}
      <Box sx={{ px: 2, py: 1.5 }}>
        <Typography
          variant="caption"
          sx={{
            color: '#6B6760',
            textTransform: 'uppercase',
            letterSpacing: '0.12em',
            fontSize: '0.55rem',
            fontWeight: 600,
          }}
        >
          Active Ticker
        </Typography>
        <Autocomplete
          value={ticker}
          onChange={(_, v) => v && setTicker(v)}
          options={tickers}
          size="small"
          disableClearable
          sx={{ mt: 0.5 }}
          renderInput={(params) => (
            <TextField
              {...params}
              variant="outlined"
              size="small"
              sx={{
                '& .MuiOutlinedInput-root': {
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  color: '#0382B7',
                },
              }}
            />
          )}
        />
      </Box>

      <Divider />

      {/* Navigation */}
      <List sx={{ flexGrow: 1, px: 1, py: 1.5 }}>
        {NAV_ITEMS.map((item) => {
          const isActive =
            pathname === item.path ||
            (item.path !== '/' && pathname.startsWith(item.path));
          return (
            <ListItemButton
              key={item.path}
              onClick={() => {
                router.push(item.path);
                if (isMobile) setMobileOpen(false);
              }}
              sx={{
                borderRadius: 1.5,
                mb: 0.5,
                py: 0.75,
                backgroundColor: isActive ? 'rgba(201,107,174,0.06)' : 'transparent',
                borderLeft: isActive ? '3px solid #C96BAE' : '3px solid transparent',
                '&:hover': {
                  backgroundColor: isActive
                    ? 'rgba(201,107,174,0.08)'
                    : 'rgba(0,0,0,0.03)',
                },
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 34,
                  color: isActive ? '#C96BAE' : '#9A9590',
                  '& .MuiSvgIcon-root': { fontSize: '1.15rem' },
                }}
              >
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.label}
                slotProps={{
                  primary: {
                    sx: {
                      fontSize: '0.82rem',
                      fontWeight: isActive ? 600 : 400,
                  color: isActive ? '#C96BAE' : '#9A9590',
                      letterSpacing: '0.01em',
                    },
                  },
                }}
              />
            </ListItemButton>
          );
        })}
      </List>

      <Divider />

      {/* Footer */}
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" sx={{ color: '#C4BFB5', fontSize: '0.58rem' }}>
          DAMG 7374 &middot; FinSage v2.0
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* App Bar (mobile) */}
      {isMobile && (
        <AppBar position="fixed" sx={{ zIndex: theme.zIndex.drawer + 1 }}>
          <Toolbar sx={{ minHeight: 48 }}>
            <IconButton
              color="inherit"
              edge="start"
              onClick={() => setMobileOpen(!mobileOpen)}
              sx={{ mr: 1 }}
            >
              <MenuIcon />
            </IconButton>
            <Typography
              sx={{
                fontFamily: '"DM Serif Display", Georgia, serif',
                fontSize: '1.05rem',
                color: '#2C2A25',
              }}
            >
              FinSage
            </Typography>
            <Box
              sx={{
                ml: 'auto',
                px: 1.5,
                py: 0.25,
                borderRadius: '6px',
                backgroundColor: 'rgba(3,130,183,0.06)',
                border: '1px solid rgba(3,130,183,0.12)',
              }}
            >
              <Typography
                sx={{ color: '#0382B7', fontWeight: 600, fontSize: '0.8rem' }}
              >
                {ticker}
              </Typography>
            </Box>
          </Toolbar>
        </AppBar>
      )}

      {/* Sidebar */}
      <Drawer
        variant={isMobile ? 'temporary' : 'permanent'}
        open={isMobile ? mobileOpen : true}
        onClose={() => setMobileOpen(false)}
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
          },
        }}
      >
        {drawerContent}
      </Drawer>

      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          mt: isMobile ? '48px' : 0,
          minHeight: '100vh',
          backgroundColor: '#FAFAF7',
          overflow: 'auto',
        }}
      >
        {/* Page header */}
        {currentPage && (
          <Box sx={{ mb: 3, display: 'flex', alignItems: 'baseline', gap: 1.5 }}>
            <Typography
              variant="h4"
              sx={{
                fontFamily: '"DM Serif Display", Georgia, serif',
                fontWeight: 400,
              }}
            >
              {currentPage.label}
            </Typography>
            <Box
              sx={{
                px: 1.5,
                py: 0.25,
                borderRadius: '6px',
                backgroundColor: 'rgba(248,203,134,0.10)',
                border: '1px solid rgba(248,203,134,0.25)',
              }}
            >
              <Typography
                sx={{
                  color: '#F8CB86',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  letterSpacing: '0.03em',
                }}
              >
                {ticker}
              </Typography>
            </Box>
          </Box>
        )}
        {children}
      </Box>
    </Box>
  );
}
