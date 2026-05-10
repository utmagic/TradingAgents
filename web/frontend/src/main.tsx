import React from 'react'
import { createRoot } from 'react-dom/client'
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import { App } from './App'

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1f6fff' },
    secondary: { main: '#0f4fd6' },
    background: { default: '#f3f7ff', paper: '#ffffff' }
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily: '"Nunito Sans", "Pretendard", "Segoe UI", sans-serif',
    h5: { fontWeight: 800 },
    h6: { fontWeight: 800 }
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          boxShadow: '0 10px 28px rgba(31, 111, 255, 0.08)'
        }
      }
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 999,
          textTransform: 'none',
          fontWeight: 700
        }
      }
    }
  }
})

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>
)
