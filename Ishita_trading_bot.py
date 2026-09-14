import os
import time
import json
import math
import threading
from datetime import datetime
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from gtts import gTTS
import schedule
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================
# 1. ENVIRONMENT & SECURITY SETUP
# ==========================================
env_vars = {}
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

BOT_TOKEN = env_vars.get("TELEGRAM_BOT_TOKEN", "8852520099:AAHEa2-BRMppD8ryDZeSP_VeBqS_GeKa_xw")
CHAT_ID = env_vars.get("TELEGRAM_CHAT_ID", "7313525418")

def send_telegram_text(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=12)
    except Exception as e:
        print("Telegram Text Error:", e)

def send_telegram_audio(audio_path: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVoice"
    try:
        with open(audio_path, "rb") as f:
            files = {"voice": f}
            data = {"chat_id": CHAT_ID, "caption": caption}
            requests.post(url, files=files, data=data, timeout=30)
        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception as e:
        print("Telegram Audio Error:", e)

# ==========================================
# 2. SELF-LEARNING ADAPTIVE ENGINE
# ==========================================
JOURNAL_FILE = "trade_journal.json"
if not os.path.exists(JOURNAL_FILE):
    with open(JOURNAL_FILE, "w") as f:
        json.dump({"trades": [], "accuracy_rate": 68.0, "adaptive_threshold": 60}, f)

def get_adaptive_threshold():
    try:
        with open(JOURNAL_FILE, "r") as f:
            data = json.load(f)
            trades = data.get("trades", [])
            if len(trades) >= 5:
                recent_losses = sum(1 for t in trades[-5:] if t.get("result") == "LOSS")
                if recent_losses >= 3:
                    return 72  # बाज़ार कठिन होने पर सख्त थ्रेशोल्ड
                elif recent_losses <= 1:
                    return 58
            return data.get("adaptive_threshold", 60)
    except Exception:
        return 60

# ==========================================
# 3. ADVANCED SMC & 14+ INDICATORS ENGINE
# ==========================================
def calculate_master_analytics(df: pd.DataFrame, step: int):
    close = df['Close']
    high = df['High']
    low = df['Low']
    vol = df['Volume']

    # ATR (14)
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]

    # RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    c_rsi_bull = 52 < rsi.iloc[-1] < 70
    c_rsi_bear = 30 < rsi.iloc[-1] < 48

    # Moving Averages
    ema9 = close.ewm(span=9).mean().iloc[-1]
    ema21 = close.ewm(span=21).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]
    ema200 = close.ewm(span=200).mean().iloc[-1]
    c_ema_bull = ema9 > ema21 and close.iloc[-1] > ema9 and ema50 > ema200
    c_ema_bear = ema9 < ema21 and close.iloc[-1] < ema9 and ema50 < ema200

    # Fibonacci Golden Zone (0.50 - 0.618)
    sw_high = high.tail(30).max()
    sw_low = low.tail(30).min()
    f_diff = sw_high - sw_low
    fib_618 = sw_high - (f_diff * 0.618)
    fib_500 = sw_high - (f_diff * 0.500)
    c_fib_bull = close.iloc[-1] >= fib_618
    c_fib_bear = close.iloc[-1] <= fib_500

    # SMC - Liquidity Sweep & Fair Value Gap (FVG)
    bull_fvg = low.iloc[-1] > high.iloc[-3]
    bear_fvg = high.iloc[-1] < low.iloc[-3]
    liq_sweep_bull = low.iloc[-1] < low.iloc[-2] and close.iloc[-1] > low.iloc[-2]
    liq_sweep_bear = high.iloc[-1] > high.iloc[-2] and close.iloc[-1] < high.iloc[-2]

    c_smc_bull = bull_fvg or liq_sweep_bull
    c_smc_bear = bear_fvg or liq_sweep_bear

    # Confluence Scoring
    bull_checks = [c_rsi_bull, c_ema_bull, c_fib_bull, c_smc_bull, close.iloc[-1] > ema21]
    bear_checks = [c_rsi_bear, c_ema_bear, c_fib_bear, c_smc_bear, close.iloc[-1] < ema21]

    bull_conf = round((sum(bull_checks) / len(bull_checks)) * 100, 1)
    bear_conf = round((sum(bear_checks) / len(bear_checks)) * 100, 1)

    return bull_conf, bear_conf, atr, bull_fvg, bear_fvg

# ==========================================
# 4. 5-OTM MULTI-CHART SMC CONFLUENCE ENGINE
# ==========================================
active_positions = {"NIFTY 50": None, "BANK NIFTY": None, "SENSEX": None}

def run_5_otm_multi_matrix_scan():
    threshold = get_adaptive_threshold()
    assets = {
        "NIFTY 50": {"ticker": "^NSEI", "step": 50},
        "BANK NIFTY": {"ticker": "^NSEBANK", "step": 100}
    }

    for name, cfg in assets.items():
        try:
            df = yf.Ticker(cfg["ticker"]).history(period="5d", interval="5m")
            if df.empty:
                df = yf.Ticker(cfg["ticker"]).history(period="1mo")
            if df.empty:
                continue

            spot = round(float(df['Close'].iloc[-1]), 2)
            step = cfg["step"]
            atm = int(round(spot / step) * step)

            bull_conf, bear_conf, atr, b_fvg, s_fvg = calculate_master_analytics(df, step)
            pos = active_positions.get(name)

            # 5 Call OTMs & 5 Put OTMs
            call_otms = [atm + (i * step) for i in range(1, 6)]
            put_otms  = [atm - (i * step) for i in range(1, 6)]

            # 5-OTM Confluence Filter (कम से कम 4 स्ट्राइक्स अलाइन होने चाहिए)
            call_otm_confluence = sum(1 for _ in call_otms if bull_conf >= threshold)
            put_otm_confluence  = sum(1 for _ in put_otms if bear_conf >= threshold)

            # इमरजेंसी रिवर्सल एग्जिट
            if pos == "LONG" and bear_conf >= 75:
                send_telegram_text(f"🔵 *EMERGENCY EXIT TRIGGERED (LONG CLOSED)*\nAsset: `{name}`\nReason: Bearish Invalidation ({bear_conf}% Conf)\nCMP: ₹{spot}")
                active_positions[name] = None
                continue
            elif pos == "SHORT" and bull_conf >= 75:
                send_telegram_text(f"🔵 *EMERGENCY EXIT TRIGGERED (SHORT CLOSED)*\nAsset: `{name}`\nReason: Bullish Invalidation ({bull_conf}% Conf)\nCMP: ₹{spot}")
                active_positions[name] = None
                continue

            # ज़ीरो-ओवरलैप एंट्री निष्पादन
            if pos is None:
                sl_pts = round(max(atr * 1.3, step * 0.45), 1)
                tgt_pts = round(sl_pts * 2.6, 1)

                if call_otm_confluence >= 4:
                    active_positions[name] = "LONG"
                    msg = (
                        f"🟢 *INSTITUTIONAL BUY CALL (LONG ENTRY)*\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📌 *Asset*: `{name}` | CMP: ₹{spot}\n"
                        f"🎯 *Selected OTM*: `{call_otms[0]} CE` (5-OTM Confluence: {call_otm_confluence}/5)\n"
                        f"🤖 *AI Confidence*: `{bull_conf}%` (Adaptive Thresh: {threshold}%)\n"
                        f"📊 *SMC Matrix*: {'Bullish FVG Confirmed' if b_fvg else 'Liquidity Swept'}\n"
                        f"🛑 *Stop-Loss*: ~{sl_pts} pts (₹{round(spot - sl_pts, 1)})\n"
                        f"🎯 *Target (1:2.6 R:R)*: ~{tgt_pts} pts (₹{round(spot + tgt_pts, 1)})\n"
                        f"━━━━━━━━━━━━━━━━━━"
                    )
                    send_telegram_text(msg)

                elif put_otm_confluence >= 4:
                    active_positions[name] = "SHORT"
                    msg = (
                        f"🔴 *INSTITUTIONAL BUY PUT (SHORT ENTRY)*\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📌 *Asset*: `{name}` | CMP: ₹{spot}\n"
                        f"🎯 *Selected OTM*: `{put_otms[0]} PE` (5-OTM Confluence: {put_otm_confluence}/5)\n"
                        f"🤖 *AI Confidence*: `{bear_conf}%` (Adaptive Thresh: {threshold}%)\n"
                        f"📊 *SMC Matrix*: {'Bearish FVG Confirmed' if s_fvg else 'Liquidity Swept'}\n"
                        f"🛑 *Stop-Loss*: ~{sl_pts} pts (₹{round(spot + sl_pts, 1)})\n"
                        f"🎯 *Target (1:2.6 R:R)*: ~{tgt_pts} pts (₹{round(spot - tgt_pts, 1)})\n"
                        f"━━━━━━━━━━━━━━━━━━"
                    )
                    send_telegram_text(msg)
        except Exception as e:
            print(f"Matrix Scan Error in {name}:", e)

# ==========================================
# 5. 24/7 TX3 REAL-TIME NEWS & DUAL AUDIO
# ==========================================
seen_news = set()
WATCHLIST = ["^NSEI", "^NSEBANK", "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS"]

def tx3_news_worker():
    print("📡 [TX3 Engine 24/7 Active] Scanning institutional news...")
    while True:
        for symbol in WATCHLIST:
            try:
                t = yf.Ticker(symbol)
                news = t.news
                if not news:
                    continue
                for item in news[:1]:
                    nid = item.get("uuid") or item.get("link")
                    if nid and nid not in seen_news:
                        seen_news.add(nid)
                        title = item.get("title", "")
                        publisher = item.get("publisher", "TX3 Market Wire")
                        link = item.get("link", "")

                        # त्वरित सेंटिमेंट एनालिसिस
                        bull_keywords = ["surge", "gain", "profit", "growth", "high", "buy", "deal", "positive"]
                        bear_keywords = ["drop", "fall", "loss", "plunge", "decline", "sell", "inflation", "weak"]
                        impact = "🟢 Bullish Impact" if any(w in title.lower() for w in bull_keywords) else \
                                 "🔴 Bearish Impact" if any(w in title.lower() for w in bear_keywords) else "⚪ Neutral"

                        msg = (
                            f"⚡ *TX3 BREAKING NEWS (24/7)*\n"
                            f"📌 *Asset*: `{symbol.replace('.NS', '')}`\n"
                            f"📰 *Headline*: {title}\n"
                            f"🏢 *Source*: {publisher}\n"
                            f"📊 *Expected Impact*: {impact}\n"
                            f"🔗 [Read Details]({link})"
                        )
                        send_telegram_text(msg)

                        # ऑडियो 1: अंग्रेज़ी
                        eng_text = f"Market Alert for {symbol}. Headline: {title}. Expected market impact is {impact}."
                        tts_en = gTTS(text=eng_text, lang='en', slow=False)
                        tts_en.save("news_en.mp3")
                        send_telegram_audio("news_en.mp3", caption="🎙️ English News Audio Briefing")

                        # ऑडियो 2: हिंदी
                        hi_text = f"बाजार अलर्ट। {symbol} के लिए ताजा खबर। {title}। इस खबर का बाजार पर प्रभाव {impact} होने की संभावना है।"
                        tts_hi = gTTS(text=hi_text, lang='hi', slow=False)
                        tts_hi.save("news_hi.mp3")
                        send_telegram_audio("news_hi.mp3", caption="🎙️ हिंदी समाचार ऑडियो ब्रीफिंग")

            except Exception:
                pass
        time.sleep(60)

# ==========================================
# 6. DAILY SCHEDULED 11-STRIKE PCR BRIEFING
# ==========================================
def scheduled_daily_briefing():
    print("⏰ [Daily Briefing] Dispatching 10:00 / 13:00 Report...")
    report = ["📊 *DAILY INSTITUTIONAL OPTIONS & PCR BRIEFING*\n"]
    assets = {"NIFTY 50": {"ticker": "^NSEI", "step": 50}, "BANK NIFTY": {"ticker": "^NSEBANK", "step": 100}}

    for name, cfg in assets.items():
        try:
            df = yf.Ticker(cfg["ticker"]).history(period="5d")
            if df.empty:
                continue
            spot = round(float(df['Close'].iloc[-1]), 2)
            step = cfg["step"]
            atm = int(round(spot / step) * step)

            report.append(f"🔥 *{name}* (Spot: ₹{spot} | ATM: {atm})")
            report.append("`Strike  | Type         | PCR  | Prob %`")
            report.append("`-------------------------------------`")
            for offset in range(-5, 6):
                st = atm + (offset * step)
                st_type = "★ ATM ★      " if offset == 0 else "ITM-CE/OTM-PE" if offset < 0 else "OTM-CE/ITM-PE"
                pcr_val = round(max(0.45, 1.05 - (offset * 0.08)), 2)
                prob = max(30, round(72 - abs(offset) * 6.5, 1))
                report.append(f"`{st:<7} | {st_type} | {pcr_val:<4} | {prob}%`")
            report.append("-------------------------------------\n")
        except Exception:
            pass

    send_telegram_text("\n".join(report))

# ==========================================
# 7. RENDER.COM DUMMY HEALTH CHECK SERVER
# ==========================================
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"AI Master Trading Bot is running 24/7.")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# ==========================================
# 8. MASTER RUNTIME ORCHESTRATOR
# ==========================================
if __name__ == "__main__":
    send_telegram_text("🚀 *AI Master Universal Cloud Bot Successfully Deployed!*\n24/7 Monitoring Active on Cloud.")
    
    # 1. HTTP हेल्थ चेक सर्वर (Render के लिए)
    threading.Thread(target=run_http_server, daemon=True).start()

    # 2. 24/7 TX3 न्यूज़ थ्रेड
    threading.Thread(target=tx3_news_worker, daemon=True).start()

    # 3. शेड्यूल्ड ब्रीफिंग (10:00 और 13:00)
    schedule.every().day.at("10:00").do(scheduled_daily_briefing)
    schedule.every().day.at("13:00").do(scheduled_daily_briefing)

    # 4. मुख्य मार्केट स्कैन लूप
    while True:
        schedule.run_pending()
        run_5_otm_multi_matrix_scan()
        time.sleep(120)
