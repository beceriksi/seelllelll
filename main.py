# main.py
import os
import time
import ccxt
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# ---------------- Config ----------------
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Majör coin listesi (Binance spot semboller)
COINS = ["BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","XRP/USDT","ADA/USDT",
         "AVAX/USDT","DOGE/USDT","DOT/USDT","LINK/USDT","MATIC/USDT","LTC/USDT"]

TF = "4h"
LIMIT = 500  # yeterli geçmiş mum
MIN_ROWS = 60

VOL_MULT = 1.5  # hacim spike eşiği
ORDERBLOCK_DIST_PCT = 0.8  # orderblock'a %0.8 yakınsa (0.8%) etki (yüzde)

exchange = ccxt.binance({"enableRateLimit": True})

# ---------------- Helpers ----------------
def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        print("Telegram bilgileri yok, mesaj atılamadı.")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode":"HTML"})
        return resp.status_code == 200
    except Exception as e:
        print("Telegram error:", e)
        return False

def fetch_ohlcv(symbol, timeframe=TF, limit=LIMIT):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not data:
            return None
        df = pd.DataFrame(data, columns=["ts","open","high","low","close","volume"])
        df["time"] = pd.to_datetime(df["ts"], unit='ms')
        df = df.reset_index(drop=True)
        return df
    except Exception as e:
        print(f"fetch_ohlcv error {symbol}: {e}")
        return None

def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def macd_hist(series, fast=12, slow=26, signal=9):
    fast_ema = series.ewm(span=fast, adjust=False).mean()
    slow_ema = series.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - macd_signal
    return macd_line, macd_signal, hist

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.rolling(period, min_periods=1).mean()
    ma_down = down.rolling(period, min_periods=1).mean().replace(0, 1e-9)
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def find_last_engulfing(df, lookback=80):
    """
    Basit orderblock proxy: son bullish veya bearish engulfing mumunu bul.
    Returns tuple (type, index, price_level)
      type: "bull" or "bear" or None
      price_level: low for bull, high for bear
    """
    n = min(len(df)-1, lookback)
    for i in range(len(df)-1, len(df)-n-1, -1):
        if i <= 0: break
        prev = df.iloc[i-1]
        curr = df.iloc[i]
        # bullish engulfing: prev down (close<open), curr up and body engulfs prev body
        if (prev['close'] < prev['open']) and (curr['close'] > curr['open']) and (curr['close'] - curr['open'] > prev['open'] - prev['close']):
            return "bull", i, float(curr['low'])
        # bearish engulfing
        if (prev['close'] > prev['open']) and (curr['close'] < curr['open']) and (curr['open'] - curr['close'] > prev['close'] - prev['open']):
            return "bear", i, float(curr['high'])
    return None, None, None

