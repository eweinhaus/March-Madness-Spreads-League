import { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

/**
 * Sport configuration context for the app.
 * Fetches sport mode and display config from the backend on mount.
 */

const SportConfigContext = createContext(null);

const DEFAULT_CONFIG = {
  sport_mode: 'football',
  display_name: 'Spread Pools',
  season_label: 'Current Season',
  pick_noun: 'game',
  period_type: 'week',
};

export function SportConfigProvider({ children }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        // Determine API URL
        const isDev = import.meta.env.MODE === 'development';
        const rawApiUrl = import.meta.env.VITE_API_URL;
        const apiUrl =
          (typeof rawApiUrl === 'string' && rawApiUrl.trim() !== ''
            ? rawApiUrl.trim().replace(/\/$/, '')
            : '') || (isDev ? 'http://localhost:8000' : '');

        if (!apiUrl) {
          throw new Error('API_URL not configured');
        }

        // Fetch sport config (no auth required)
        const response = await axios.get(`${apiUrl}/app-config`);
        setConfig(response.data);
        setError(null);
      } catch (err) {
        console.warn('Failed to fetch sport config from backend, using fallback:', err.message);
        
        // Fallback to VITE_SPORT_MODE or default to football
        const fallbackMode = import.meta.env.VITE_SPORT_MODE || 'football';
        const fallbackConfig = {
          sport_mode: fallbackMode,
          display_name: fallbackMode === 'march_madness' ? 'March Madness' : 'Football Season',
          season_label: fallbackMode === 'march_madness' ? 'Tournament' : 'Season',
          pick_noun: fallbackMode === 'march_madness' ? 'matchup' : 'game',
          period_type: fallbackMode === 'march_madness' ? 'round' : 'week',
        };
        
        setConfig(fallbackConfig);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchConfig();
  }, []);

  return (
    <SportConfigContext.Provider value={{ config: config || DEFAULT_CONFIG, loading, error }}>
      {children}
    </SportConfigContext.Provider>
  );
}

export function useSportConfig() {
  const context = useContext(SportConfigContext);
  if (!context) {
    throw new Error('useSportConfig must be used within SportConfigProvider');
  }
  return context;
}
