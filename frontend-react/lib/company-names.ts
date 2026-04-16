/**
 * Static ticker → company name mapping for tracked tickers.
 * Mirrors the orchestrator's _COMPANY_NAME_CACHE + config/tickers.yaml.
 */

export const COMPANY_NAMES: Record<string, string> = {
  // Technology
  AAPL: 'Apple Inc.',
  MSFT: 'Microsoft Corporation',
  NVDA: 'NVIDIA Corporation',
  GOOGL: 'Alphabet Inc.',
  META: 'Meta Platforms Inc.',
  AVGO: 'Broadcom Inc.',
  ORCL: 'Oracle Corporation',
  CRM: 'Salesforce Inc.',
  ADBE: 'Adobe Inc.',
  AMD: 'Advanced Micro Devices Inc.',

  // Consumer / Retail
  AMZN: 'Amazon.com Inc.',
  TSLA: 'Tesla Inc.',
  WMT: 'Walmart Inc.',
  HD: 'The Home Depot Inc.',
  MCD: "McDonald's Corporation",
  NKE: 'Nike Inc.',
  COST: 'Costco Wholesale Corporation',
  PEP: 'PepsiCo Inc.',
  KO: 'The Coca-Cola Company',
  PG: 'Procter & Gamble Co.',

  // Finance
  JPM: 'JPMorgan Chase & Co.',
  V: 'Visa Inc.',
  MA: 'Mastercard Incorporated',
  BAC: 'Bank of America Corp.',
  WFC: 'Wells Fargo & Company',
  GS: 'Goldman Sachs Group Inc.',
  MS: 'Morgan Stanley',
  BLK: 'BlackRock Inc.',
  AXP: 'American Express Company',
  C: 'Citigroup Inc.',

  // Healthcare
  UNH: 'UnitedHealth Group Inc.',
  JNJ: 'Johnson & Johnson',
  LLY: 'Eli Lilly and Company',
  ABBV: 'AbbVie Inc.',
  PFE: 'Pfizer Inc.',
  MRK: 'Merck & Co. Inc.',
  TMO: 'Thermo Fisher Scientific Inc.',
  ABT: 'Abbott Laboratories',
  DHR: 'Danaher Corporation',
  BMY: 'Bristol-Myers Squibb Company',

  // Energy / Industrial / Other
  XOM: 'Exxon Mobil Corporation',
  CVX: 'Chevron Corporation',
  LIN: 'Linde plc',
  NEE: 'NextEra Energy Inc.',
  UNP: 'Union Pacific Corporation',
  RTX: 'RTX Corporation',
  HON: 'Honeywell International Inc.',
  CAT: 'Caterpillar Inc.',
  BA: 'The Boeing Company',
  NFLX: 'Netflix Inc.',
};

export function getCompanyName(ticker: string): string | null {
  return COMPANY_NAMES[ticker.toUpperCase().trim()] ?? null;
}
