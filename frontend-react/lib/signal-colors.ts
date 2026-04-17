const GREEN = '#1A9E60';
const AMBER = '#C08C00';
const RED = '#C9392C';
const DEFAULT = '#03B792';

const SIGNAL_MAP: Record<string, string> = {
  BULLISH: GREEN,
  STRONG_GROWTH: GREEN,
  EXCELLENT: GREEN,
  HEALTHY: GREEN,
  MODERATE_GROWTH: AMBER,
  NEUTRAL: AMBER,
  MIXED: AMBER,
  FAIR: AMBER,
  BEARISH: RED,
  DECLINING: RED,
  UNPROFITABLE: RED,
};

export function getSignalColor(signal?: string | null): string {
  if (!signal) return DEFAULT;
  return SIGNAL_MAP[signal.toUpperCase().replace(/\s+/g, '_')] || DEFAULT;
}
