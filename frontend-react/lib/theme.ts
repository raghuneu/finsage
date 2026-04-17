'use client';

import { createTheme } from '@mui/material/styles';

// ── Fancy Flirt Palette ──────────────────────────────────────
// Cerulean (RGB)     #0382B7  — Primary / Interactive
// Rare Jade          #9DCBB8  — Success / Bullish
// Jade Accent        #03B792  — Accent / Active nav
// Trendy Coral       #E58B6D  — Warning / Bearish
// Sky Yellow         #F8CB86  — Highlight / Charts
// Cookies And Cream  #EBE1B2  — Warm neutral accent

const theme = createTheme({
  palette: {
    mode: 'light',
    background: {
      default: '#F4F2ED',
      paper: '#FFFFFF',
    },
    primary: {
      main: '#0382B7',
      light: '#2A9DD0',
      dark: '#026A95',
    },
    secondary: {
      main: '#03B792',
      light: '#36CCAB',
      dark: '#029574',
    },
    success: {
      main: '#9DCBB8',
      light: '#B5D9CB',
      dark: '#7AB39C',
    },
    error: {
      main: '#E58B6D',
      light: '#ECA68E',
      dark: '#D06A49',
    },
    warning: {
      main: '#F8CB86',
      light: '#FAD9A4',
      dark: '#E5B05E',
    },
    text: {
      primary: '#2C2A25',
      secondary: '#6B6760',
    },
    divider: '#E8E4DB',
  },
  typography: {
    fontFamily: '"DM Sans", "Helvetica Neue", sans-serif',
    h4: {
      fontFamily: '"DM Serif Display", Georgia, serif',
      fontWeight: 400,
      fontSize: '1.65rem',
      letterSpacing: '-0.01em',
      color: '#2C2A25',
    },
    h5: {
      fontFamily: '"DM Serif Display", Georgia, serif',
      fontWeight: 400,
      fontSize: '1.3rem',
      color: '#2C2A25',
    },
    h6: {
      fontFamily: '"DM Serif Display", Georgia, serif',
      fontWeight: 400,
      fontSize: '1.05rem',
      color: '#2C2A25',
    },
    body1: {
      fontSize: '0.9rem',
      lineHeight: 1.65,
    },
    body2: {
      color: '#6B6760',
      fontSize: '0.85rem',
    },
    caption: {
      color: '#9A9590',
      fontSize: '0.75rem',
    },
  },
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#F4F2ED',
          scrollbarWidth: 'thin',
          scrollbarColor: '#D8D4CB transparent',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          background: '#FFFFFF',
          border: '1px solid #E8E4DB',
          backgroundImage: 'none',
          boxShadow: '0 1px 3px rgba(44,42,37,0.04)',
          transition: 'border-color 0.25s ease, box-shadow 0.25s ease',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#F2F0EB',
          borderRight: '1px solid #E8E4DB',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#F4F2ED',
          borderBottom: '1px solid #E8E4DB',
          boxShadow: 'none',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          fontSize: '0.75rem',
          fontFamily: '"DM Sans", sans-serif',
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
          fontSize: '0.875rem',
          fontFamily: '"DM Sans", sans-serif',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          fontFamily: '"DM Sans", sans-serif',
          borderRadius: 8,
        },
      },
      variants: [
        {
          props: { variant: 'contained', color: 'primary' },
          style: {
            background: '#03B792',
            color: '#FFFFFF',
            boxShadow: '0 2px 12px rgba(3,183,146,0.2)',
            '&:hover': {
              background: '#36CCAB',
              boxShadow: '0 4px 20px rgba(3,183,146,0.3)',
            },
          },
        },
      ],
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            '& fieldset': {
              borderColor: '#E8E4DB',
            },
            '&:hover fieldset': {
              borderColor: '#D8D4CB',
            },
            '&.Mui-focused fieldset': {
              borderColor: '#03B792',
            },
          },
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: '#E8E4DB',
        },
      },
    },
  },
});

export default theme;
