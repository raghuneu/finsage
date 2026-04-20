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
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import MenuIcon from '@mui/icons-material/Menu';
import { useTicker } from '@/lib/ticker-context';
import { getCompanyName } from '@/lib/company-names';

const DRAWER_WIDTH = 220;

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/', icon: <DashboardIcon /> },
  { label: 'Analytics', path: '/analytics', icon: <BarChartIcon /> },
  { label: 'SEC Filings', path: '/sec', icon: <DescriptionIcon /> },
  { label: 'Report', path: '/report', icon: <ArticleIcon /> },
  { label: 'Observability', path: '/observability', icon: <MonitorHeartIcon /> },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { ticker, setTicker, tickers, companyName, validating, invalidTicker } = useTicker();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);

  const currentPage = NAV_ITEMS.find(
    (item) => pathname === item.path || (item.path !== '/' && pathname.startsWith(item.path))
  ) || (pathname.startsWith('/architecture') ? { label: 'Architecture', path: '/architecture', icon: <AccountTreeIcon /> } : undefined);

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
            background: 'linear-gradient(90deg, #03B792 0%, #0382B7 60%, transparent 100%)',
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
          freeSolo
          autoSelect
          value={ticker}
          onChange={(_, v) => v && setTicker(v as string)}
          options={tickers}
          size="small"
          disableClearable
          sx={{ mt: 0.5, backgroundColor: 'rgba(3,130,183,0.06)', border: '1px solid rgba(3,130,183,0.15)', borderRadius: '8px' }}
          renderOption={(props, option) => (
            <li {...props} key={option}>
              <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, color: '#0382B7' }}>
                  {option}
                </Typography>
                {getCompanyName(option) && (
                  <Typography sx={{ fontSize: '0.65rem', color: '#9A9590', lineHeight: 1.2 }}>
                    {getCompanyName(option)}
                  </Typography>
                )}
              </Box>
            </li>
          )}
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
        {validating && (
          <Typography
            sx={{
              mt: 0.5,
              fontSize: '0.6rem',
              color: '#0382B7',
              lineHeight: 1.2,
              px: 0.5,
            }}
          >
            Validating ticker...
          </Typography>
        )}
        {invalidTicker && (
          <Typography
            sx={{
              mt: 0.5,
              fontSize: '0.6rem',
              color: '#ef476f',
              fontWeight: 600,
              lineHeight: 1.2,
              px: 0.5,
            }}
          >
            {invalidTicker} is not a valid ticker
          </Typography>
        )}
        {!validating && !invalidTicker && companyName && (
          <Typography
            sx={{
              mt: 0.5,
              fontSize: '0.62rem',
              color: '#9A9590',
              lineHeight: 1.2,
              px: 0.5,
            }}
          >
            {companyName}
          </Typography>
        )}
      </Box>

      <Divider />

      {/* Navigation */}
      <List sx={{ px: 1, py: 1.5 }}>
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
                backgroundColor: isActive ? 'rgba(0,0,0,0.06)' : 'transparent',
                borderLeft: isActive ? '3px solid #03B792' : '3px solid transparent',
                '&:hover': {
                  backgroundColor: isActive
                    ? 'rgba(0,0,0,0.06)'
                    : 'rgba(0,0,0,0.03)',
                },
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 34,
                  color: isActive ? '#2C2A25' : '#6B7280',
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
                  color: isActive ? '#2C2A25' : '#6B7280',
                      letterSpacing: '0.01em',
                    },
                  },
                }}
              />
            </ListItemButton>
          );
        })}
      </List>

      {/* Spacer pushes Architecture + Footer to bottom */}
      <Box sx={{ flexGrow: 1 }} />

      {/* Architecture — pinned above footer */}
      <Box sx={{ px: 1, pb: 0.5 }}>
        {(() => {
          const isActive = pathname.startsWith('/architecture');
          return (
            <ListItemButton
              onClick={() => {
                router.push('/architecture');
                if (isMobile) setMobileOpen(false);
              }}
              sx={{
                borderRadius: 1.5,
                py: 0.75,
                backgroundColor: isActive ? 'rgba(0,0,0,0.06)' : 'transparent',
                borderLeft: isActive ? '3px solid #03B792' : '3px solid transparent',
                '&:hover': {
                  backgroundColor: isActive
                    ? 'rgba(0,0,0,0.06)'
                    : 'rgba(0,0,0,0.03)',
                },
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 34,
                  color: isActive ? '#2C2A25' : '#6B7280',
                  '& .MuiSvgIcon-root': { fontSize: '1.15rem' },
                }}
              >
                <AccountTreeIcon />
              </ListItemIcon>
              <ListItemText
                primary="Architecture"
                slotProps={{
                  primary: {
                    sx: {
                      fontSize: '0.82rem',
                      fontWeight: isActive ? 600 : 400,
                      color: isActive ? '#2C2A25' : '#6B7280',
                      letterSpacing: '0.01em',
                    },
                  },
                }}
              />
            </ListItemButton>
          );
        })()}
      </Box>

      <Divider />

      {/* Footer */}
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
          Built by FinSage Team
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
          <a href="https://www.linkedin.com/in/srraghuram/" target="_blank" rel="noopener noreferrer" style={{ color: '#6B7280', textDecoration: 'none', fontSize: '0.6rem' }}>Raghu</a>
          <a href="https://www.linkedin.com/in/shrirangesh-v26/" target="_blank" rel="noopener noreferrer" style={{ color: '#6B7280', textDecoration: 'none', fontSize: '0.6rem' }}>Rangesh</a>
          <a href="https://www.linkedin.com/in/ojas-misra/" target="_blank" rel="noopener noreferrer" style={{ color: '#6B7280', textDecoration: 'none', fontSize: '0.6rem' }}>Ojas</a>
        </Box>
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
              Fin
              <Box
                component="span"
                sx={{
                  backgroundColor: 'rgba(6, 214, 160, 0.12)',
                  borderRadius: '4px',
                  px: 0.5,
                }}
              >
                Sage
              </Box>
            </Typography>
            <Box
              sx={{
                ml: 'auto',
                display: 'flex',
                alignItems: 'center',
                gap: 1,
              }}
            >
              <Box
                sx={{
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
              {companyName && (
                <Typography
                  sx={{
                    color: '#6B6760',
                    fontSize: '0.7rem',
                    fontWeight: 400,
                    maxWidth: 120,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {companyName}
                </Typography>
              )}
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
        {currentPage && pathname !== '/architecture' && (
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
                backgroundColor: 'rgba(3,130,183,0.10)',
                border: '1px solid rgba(3,130,183,0.25)',
              }}
            >
              <Typography
                sx={{
                  color: '#0382B7',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  letterSpacing: '0.03em',
                }}
              >
                {ticker}
              </Typography>
            </Box>
            {companyName && (
              <Typography
                sx={{
                  color: '#6B6760',
                  fontSize: '0.9rem',
                  fontWeight: 400,
                  whiteSpace: 'nowrap',
                }}
              >
                {companyName}
              </Typography>
            )}
          </Box>
        )}
        {children}
      </Box>
    </Box>
  );
}
