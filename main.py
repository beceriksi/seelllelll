import ccxt
import pandas as pd
import numpy as np
import os, requests, datetime

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

exchange = ccxt.binance()
exchange.load_markets()

def fetch(symbol, tf="1h"):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=200)
        return pd.DataFrame(data, columns=["t","o","h","l","c","v"])
    except:
        return None

def rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta>0, delta, 0)
    loss = np.where(delta<0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def analyze(symbol):
    df = fetch(symbol)
    if df is None or len(df) < 50: 
        return None
    
    df["ema20"] = df["c"].ewm(span=20).mean()
    df["ema50"] = df["c"].ewm(span=50).mean()
    df["rsi"] = rsi(df["c"])
    df["vol_chg"] = df["v"].pct_change() * 100
    
    last, prev = df.iloc[-1], df.iloc[-2]

    buy = last["c"] > last["ema20"] and 30 < last["rsi"] < 65 and last["vol_chg"] > 25
    sell = last["c"] < last["ema20"] and last["rsi"] > 60 and last["vol_chg"] > 20

    if buy:
        return f"✅ {symbol} AL Sinyali | RSI {last['rsi']:.1f} | Hacim +{last['vol_chg']:.0f}%"
    if sell:
        return f"⚠️ {symbol} SAT Sinyali | RSI {last['rsi']:.1f} | Hacim +{last['vol_chg']:.0f}%"
    return None

majors = ["BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","XRP/USDT","DOGE/USDT","ADA/USDT","AVAX/USDT"]

signals = []
for s in majors:
    res = analyze(s)
    if res: signals.append(res)

now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

if signals:
    send_telegram(f"📡 Piyasa Tarama ({now})\n" + "\n".join(signals))
else:
    print("Sinyal yok, sessiz çalıştı ✅")
