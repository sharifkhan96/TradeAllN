"""The tradable universe used by the simulated provider and the symbol sync.

Fields: symbol, name, exchange, sector, sector ETF, base price, beta, daily vol, market cap ($B), P/E.
"""

SECTOR_ETFS = {
    "Technology": "XLK",
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
}

STOCKS = [
    ("AAPL", "Apple Inc.", "NASDAQ", "Technology", 228, 1.15, 0.016, 3450, 34.1),
    ("MSFT", "Microsoft Corporation", "NASDAQ", "Technology", 428, 1.05, 0.015, 3180, 35.6),
    ("NVDA", "NVIDIA Corporation", "NASDAQ", "Technology", 138, 1.75, 0.031, 3390, 52.4),
    ("AMD", "Advanced Micro Devices, Inc.", "NASDAQ", "Technology", 158, 1.70, 0.030, 256, 48.0),
    ("INTC", "Intel Corporation", "NASDAQ", "Technology", 24, 1.10, 0.027, 104, None),
    ("ORCL", "Oracle Corporation", "NYSE", "Technology", 172, 1.10, 0.020, 476, 38.2),
    ("CRM", "Salesforce, Inc.", "NYSE", "Technology", 281, 1.20, 0.020, 270, 44.5),
    ("ADBE", "Adobe Inc.", "NASDAQ", "Technology", 482, 1.25, 0.021, 213, 39.9),
    ("AVGO", "Broadcom Inc.", "NASDAQ", "Technology", 221, 1.40, 0.026, 1030, 41.3),
    ("GOOGL", "Alphabet Inc. Class A", "NASDAQ", "Communication Services", 176, 1.05, 0.018, 2160, 23.4),
    ("META", "Meta Platforms, Inc.", "NASDAQ", "Communication Services", 582, 1.25, 0.022, 1470, 27.2),
    ("NFLX", "Netflix, Inc.", "NASDAQ", "Communication Services", 702, 1.30, 0.022, 300, 41.0),
    ("DIS", "The Walt Disney Company", "NYSE", "Communication Services", 101, 1.00, 0.016, 184, 36.7),
    ("AMZN", "Amazon.com, Inc.", "NASDAQ", "Consumer Discretionary", 191, 1.20, 0.019, 2010, 42.8),
    ("TSLA", "Tesla, Inc.", "NASDAQ", "Consumer Discretionary", 251, 2.00, 0.036, 805, 68.3),
    ("NKE", "NIKE, Inc.", "NYSE", "Consumer Discretionary", 79, 1.00, 0.019, 118, 22.4),
    ("SBUX", "Starbucks Corporation", "NASDAQ", "Consumer Discretionary", 96, 0.95, 0.017, 109, 29.1),
    ("MCD", "McDonald's Corporation", "NYSE", "Consumer Discretionary", 291, 0.70, 0.011, 209, 25.3),
    ("JPM", "JPMorgan Chase & Co.", "NYSE", "Financials", 221, 1.05, 0.014, 622, 12.4),
    ("BAC", "Bank of America Corporation", "NYSE", "Financials", 42, 1.20, 0.017, 325, 13.8),
    ("GS", "The Goldman Sachs Group, Inc.", "NYSE", "Financials", 521, 1.30, 0.018, 165, 15.1),
    ("V", "Visa Inc.", "NYSE", "Financials", 291, 0.90, 0.012, 570, 30.2),
    ("MA", "Mastercard Incorporated", "NYSE", "Financials", 502, 0.95, 0.012, 462, 37.4),
    ("JNJ", "Johnson & Johnson", "NYSE", "Health Care", 156, 0.55, 0.010, 375, 22.6),
    ("UNH", "UnitedHealth Group Incorporated", "NYSE", "Health Care", 522, 0.70, 0.016, 480, 21.9),
    ("PFE", "Pfizer Inc.", "NYSE", "Health Care", 28, 0.65, 0.015, 160, 19.7),
    ("LLY", "Eli Lilly and Company", "NYSE", "Health Care", 851, 0.85, 0.020, 808, 78.0),
    ("MRNA", "Moderna, Inc.", "NASDAQ", "Health Care", 41, 1.40, 0.035, 16, None),
    ("XOM", "Exxon Mobil Corporation", "NYSE", "Energy", 116, 0.90, 0.014, 510, 14.2),
    ("CVX", "Chevron Corporation", "NYSE", "Energy", 154, 0.95, 0.014, 280, 15.6),
    ("BA", "The Boeing Company", "NYSE", "Industrials", 171, 1.40, 0.022, 128, None),
    ("CAT", "Caterpillar Inc.", "NYSE", "Industrials", 362, 1.10, 0.017, 175, 16.4),
    ("GE", "GE Aerospace", "NYSE", "Industrials", 182, 1.15, 0.018, 197, 33.8),
    ("KO", "The Coca-Cola Company", "NYSE", "Consumer Staples", 68, 0.55, 0.009, 293, 25.9),
    ("PG", "The Procter & Gamble Company", "NYSE", "Consumer Staples", 166, 0.50, 0.009, 391, 26.4),
    ("WMT", "Walmart Inc.", "NYSE", "Consumer Staples", 86, 0.60, 0.011, 690, 36.0),
    ("COST", "Costco Wholesale Corporation", "NASDAQ", "Consumer Staples", 902, 0.80, 0.013, 400, 52.1),
]

# symbol, name, base price, exposure to market, (sector, loading) pairs, daily idiosyncratic vol
ETFS = [
    ("SPY", "SPDR S&P 500 ETF Trust", 562, 1.0, [], 0.0010),
    ("QQQ", "Invesco QQQ Trust", 481, 1.15, [("Technology", 0.5), ("Communication Services", 0.2)], 0.0015),
    ("DIA", "SPDR Dow Jones Industrial Average ETF", 421, 0.92, [("Industrials", 0.2)], 0.0012),
    ("IWM", "iShares Russell 2000 ETF", 216, 1.20, [], 0.0040),
    *[
        (etf, f"{sector} Select Sector SPDR Fund", price, 1.0, [(sector, 1.0)], 0.0015)
        for (sector, etf), price in zip(SECTOR_ETFS.items(), [228, 92, 196, 47, 147, 92, 133, 81], strict=True)
    ],
]

DESCRIPTIONS = {
    "Technology": "designs and sells technology products, software and services worldwide.",
    "Communication Services": "operates digital platforms, media and entertainment services.",
    "Consumer Discretionary": "sells consumer products and services across global markets.",
    "Financials": "provides banking, payments and financial services to consumers and institutions.",
    "Health Care": "discovers, develops and markets pharmaceuticals and health care services.",
    "Energy": "explores for, produces and refines oil, natural gas and petrochemicals.",
    "Industrials": "manufactures aerospace, machinery and industrial equipment.",
    "Consumer Staples": "makes and sells everyday consumer goods and groceries.",
}


# Extra sector ETFs that exist only in real-data mode (Yahoo sectors with no simulated factor).
REAL_EXTRA_ETFS = ["XLB", "XLRE", "XLU"]
ETF_SYMBOLS = {e[0] for e in ETFS} | set(REAL_EXTRA_ETFS)


# Real tickers retail investors hold most (Robinhood / Trading 212 "most popular" style).
# These load at startup; every other US ticker loads on demand when someone opens it.
POPULAR = [
    "TSLA", "NVDA", "AAPL", "AMZN", "PLTR", "AMD", "MSFT", "META", "GOOGL", "GOOG", "NFLX",
    "SOFI", "HOOD", "COIN", "MSTR", "F", "GM", "RIVN", "LCID", "NIO", "UBER", "LYFT", "ABNB",
    "SHOP", "SNAP", "PINS", "RDDT", "RBLX", "U", "DKNG", "PYPL", "XYZ", "AFRM", "UPST", "NU",
    "BABA", "PDD", "JD", "TSM", "ASML", "ARM", "SMCI", "MU", "QCOM", "TXN", "CSCO", "IBM",
    "DELL", "HPQ", "SNOW", "CRWD", "PANW", "NET", "DDOG", "ZS", "OKTA", "MDB", "TEAM", "NOW",
    "WDAY", "INTU", "ANET", "MRVL", "ON", "LRCX", "AMAT", "KLAC", "SOUN", "BBAI", "IONQ",
    "RGTI", "QBTS", "MARA", "RIOT", "CLSK", "GME", "AMC", "BB", "NOK", "T", "VZ", "TMUS",
    "WBD", "PARA", "SPOT", "ROKU", "DIS", "SBUX", "CMG", "MCD", "NKE", "LULU", "TGT", "WMT",
    "COST", "HD", "LOW", "KO", "PEP", "PG", "JNJ", "PFE", "MRNA", "LLY", "NVO", "ABBV",
    "UNH", "CVS", "HIMS", "JPM", "BAC", "WFC", "C", "GS", "MS", "SCHW", "V", "MA", "AXP",
    "BRK.B", "XOM", "CVX", "OXY", "BP", "SHEL", "ENPH", "FSLR", "PLUG", "NEE", "BA", "LMT",
    "RTX", "GE", "CAT", "DE", "AAL", "DAL", "UAL", "LUV", "CCL", "RCL", "NCLH", "MAR",
    "VOO", "VTI", "QQQM", "SCHD", "VYM", "VGT", "ARKK", "SOXL", "TQQQ", "SQQQ", "TLT",
    "GLD", "SLV", "IBIT", "ETHA", "JEPI", "VXUS", "BND", "SMH",
]


def real_universe() -> list[str]:
    from django.conf import settings

    syms = [s[0] for s in STOCKS] + [e[0] for e in ETFS] + REAL_EXTRA_ETFS
    syms += [s for s in POPULAR if s not in syms]
    for s in settings.EXTRA_SYMBOLS:
        if s not in syms:
            syms.append(s)
    return syms
