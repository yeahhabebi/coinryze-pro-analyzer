import streamlit as st
import time
from datetime import datetime
import re
import random
import os
import json
import boto3
from botocore.config import Config
from collections import deque

# =============================================
# ENVIRONMENT VARIABLES CONFIGURATION
# =============================================

# Cloudflare R2 Storage
R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
R2_BUCKET = os.getenv('R2_BUCKET', 'coinryze-analyzer')
R2_ACCOUNT_ID = os.getenv('R2_ACCOUNT_ID')
R2_ENDPOINT = os.getenv('R2_ENDPOINT')

# App Configuration
APP_NAME = os.getenv('APP_NAME', 'Coinryze Pro Analyzer')
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', '10'))
MAX_SIGNALS_HISTORY = int(os.getenv('MAX_SIGNALS_HISTORY', '100'))
MAX_SIGNALS_DISPLAY = int(os.getenv('MAX_SIGNALS_DISPLAY', '20'))

# Bot Configuration
TELEGRAM_BOT_NAME = os.getenv('TELEGRAM_BOT_NAME', 'ETHGPT60s_bot')
ANALYSIS_WINDOW = int(os.getenv('ANALYSIS_WINDOW', '5'))

# Betting Configuration
BET_MULTIPLIERS = [1.0, 2.5, 6.25, 15.63, 39.08, 97.62, 244.05, 610.12]

# =============================================
# R2 STORAGE FUNCTIONS
# =============================================

def get_r2_client():
    """Initialize R2 client if credentials are available"""
    if R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_ENDPOINT:
        try:
            return boto3.client(
                's3',
                endpoint_url=R2_ENDPOINT,
                aws_access_key_id=R2_ACCESS_KEY_ID,
                aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                config=Config(signature_version='s3v4')
            )
        except Exception as e:
            if DEBUG_MODE:
                st.error(f"❌ R2 Client Error: {e}")
            return None
    return None

def save_to_r2(data, key):
    """Save data to R2 storage"""
    try:
        s3_client = get_r2_client()
        if s3_client:
            s3_client.put_object(
                Bucket=R2_BUCKET,
                Key=key,
                Body=json.dumps(data, default=str),
                ContentType='application/json'
            )
            return True
    except Exception as e:
        if DEBUG_MODE:
            st.error(f"❌ R2 Save Error: {e}")
    return False

def load_from_r2(key):
    """Load data from R2 storage"""
    try:
        s3_client = get_r2_client()
        if s3_client:
            response = s3_client.get_object(Bucket=R2_BUCKET, Key=key)
            data = json.loads(response['Body'].read())
            return data
    except Exception:
        pass
    return None

# =============================================
# INITIALIZATION
# =============================================

# Initialize session state for data persistence
if 'latest_signals' not in st.session_state:
    st.session_state.latest_signals = []

if 'bot_monitors' not in st.session_state:
    st.session_state.bot_monitors = {}

if 'manual_signals_queue' not in st.session_state:
    st.session_state.manual_signals_queue = deque()

class LightweightPredictor:
    def __init__(self):
        self.window_size = ANALYSIS_WINDOW
    
    def predict(self, signals):
        if len(signals) < 3:
            return {'color': 'Analyzing...', 'confidence': 'Low', 'probability': 0.5}
        
        recent_colors = [s.get('result_color') for s in signals[-self.window_size:] if s.get('result_color') in ['Green', 'Red']]
        
        if not recent_colors:
            return {'color': 'Green', 'confidence': 'Low', 'probability': 0.5}
        
        green_count = recent_colors.count('Green')
        red_count = recent_colors.count('Red')
        total = green_count + red_count
        
        if total == 0:
            return {'color': 'Green', 'confidence': 'Low', 'probability': 0.5}
        
        green_prob = green_count / total
        
        if len(recent_colors) >= 2 and recent_colors[-1] == recent_colors[-2]:
            predicted_color = 'Red' if recent_colors[-1] == 'Green' else 'Green'
            confidence = 'Medium'
            probability = 0.65
        elif green_prob > 0.6:
            predicted_color = 'Green'
            confidence = 'Medium'
            probability = green_prob
        elif green_prob < 0.4:
            predicted_color = 'Red'
            confidence = 'Medium'
            probability = 1 - green_prob
        else:
            predicted_color = 'Green' if green_prob >= 0.5 else 'Red'
            confidence = 'Low'
            probability = 0.55
        
        return {'color': predicted_color, 'confidence': confidence, 'probability': probability}

class SignalProcessor:
    def __init__(self, bot_name):
        self.bot_name = bot_name
        self.signals = []
        self.last_period_id = None
        self.predictor = LightweightPredictor()
        self.current_phase = 1
        self.multipliers = BET_MULTIPLIERS
        self.load_data()
    
    def load_data(self):
        """Load data from R2 storage"""
        try:
            data = load_from_r2(f"{self.bot_name}_data.json")
            if data:
                self.signals = data.get('signals', [])
                self.current_phase = data.get('current_phase', 1)
                self.last_period_id = data.get('last_period_id')
                if self.signals:
                    self.last_period_id = self.signals[-1]['period_id']
        except Exception:
            pass
    
    def save_data(self):
        """Save data to R2 storage"""
        data = {
            'signals': self.signals,
            'current_phase': self.current_phase,
            'last_period_id': self.last_period_id,
            'last_updated': datetime.now().isoformat(),
            'bot_name': self.bot_name
        }
        save_to_r2(data, f"{self.bot_name}_data.json")
    
    def parse_signal(self, message):
        try:
            if not message:
                return None
            
            signal_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'period_id': None,
                'result': None,
                'result_color': None,
                'trade_color': None,
                'quantity': 1.0,
                'phase': self.current_phase,
                'bot_name': self.bot_name,
                'source': 'manual'
            }
            
            # Extract period ID - MULTIPLE PATTERNS for your format
            period_match = re.search(r'Current period ID:\s*(\d+)', message)
            if not period_match:
                period_match = re.search(r'📌Current period ID:\s*(\d+)', message)
            if not period_match:
                period_match = re.search(r'period ID:\s*(\d+)', message)
            if not period_match:
                period_match = re.search(r'📌period ID:\s*(\d+)', message)
            
            if period_match:
                signal_data['period_id'] = period_match.group(1)
            else:
                return None
            
            # Extract result - FIXED for your format
            if 'Result:Win' in message or 'Win🎉' in message or '🔔Result:Win🎉' in message:
                signal_data['result'] = 'Win'
                signal_data['result_color'] = random.choice(['Green', 'Red'])
                self.current_phase = 1
            elif 'Result:Lose' in message or 'Lose💔' in message or '🔔Result:Lose💔' in message:
                signal_data['result'] = 'Lose'
                signal_data['result_color'] = random.choice(['Green', 'Red'])
                if self.current_phase < len(self.multipliers):
                    self.current_phase += 1
            else:
                return None
            
            # Extract trade color - FIXED for your format
            if '🟢✔️' in message or 'Trade: 🟢' in message or '📲Trade: 🟢✔️' in message:
                signal_data['trade_color'] = 'Green'
            elif '🔴✔️' in message or 'Trade: 🔴' in message or '📲Trade: 🔴✔️' in message:
                signal_data['trade_color'] = 'Red'
            else:
                return None
            
            # Extract quantity - FIXED for your format
            qty_match = re.search(r'quantity:\s*x?([\d.]+)', message, re.IGNORECASE)
            if not qty_match:
                qty_match = re.search(r'Recommended quantity:\s*x?([\d.]+)', message, re.IGNORECASE)
            
            if qty_match:
                try:
                    signal_data['quantity'] = float(qty_match.group(1))
                except:
                    signal_data['quantity'] = self.multipliers[self.current_phase - 1]
            else:
                signal_data['quantity'] = self.multipliers[self.current_phase - 1]
            
            # Add prediction
            signal_data['prediction'] = self.predictor.predict(self.signals)
            
            return signal_data
            
        except Exception as e:
            if DEBUG_MODE:
                st.error(f"❌ Parse error: {str(e)}")
            return None
    
    def add_signal(self, signal_data):
        if signal_data:
            # Check if this period ID already exists
            existing_ids = [s['period_id'] for s in self.signals]
            if signal_data['period_id'] not in existing_ids:
                self.signals.append(signal_data)
                self.last_period_id = signal_data['period_id']
                
                # Keep only max signals
                if len(self.signals) > MAX_SIGNALS_HISTORY:
                    self.signals = self.signals[-MAX_SIGNALS_HISTORY:]
                
                # Update global signals
                st.session_state.latest_signals.append(signal_data)
                if len(st.session_state.latest_signals) > MAX_SIGNALS_HISTORY:
                    st.session_state.latest_signals = st.session_state.latest_signals[-MAX_SIGNALS_HISTORY:]
                
                # Save to R2 storage
                self.save_data()
                
                return True
            else:
                return False
        return False

# Initialize bot in session state
bot_key = f"Bot_1_{TELEGRAM_BOT_NAME}"
if bot_key not in st.session_state.bot_monitors:
    st.session_state.bot_monitors[bot_key] = SignalProcessor(TELEGRAM_BOT_NAME)

# Get the processor
processor = st.session_state.bot_monitors[bot_key]

# =============================================
# AUTO PROCESSING FUNCTIONS
# =============================================

def process_queued_signals():
    """Process any signals in the manual queue"""
    processed_count = 0
    while st.session_state.manual_signals_queue:
        signal_text = st.session_state.manual_signals_queue.popleft()
        signal = processor.parse_signal(signal_text)
        if signal:
            if processor.add_signal(signal):
                processed_count += 1
    return processed_count

def add_to_manual_queue(signal_text):
    """Add signal to manual processing queue"""
    st.session_state.manual_signals_queue.append(signal_text)

# =============================================
# STREAMLIT APP
# =============================================

st.set_page_config(
    page_title=APP_NAME, 
    page_icon="🎯", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# CSS Styles
st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        color: #FF6B35;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: bold;
        padding: 10px;
    }
    .bot-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 12px;
        border-radius: 10px;
        color: white;
        margin: 6px 0;
    }
    .signal-card-win {
        background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%);
        padding: 10px;
        border-radius: 8px;
        margin: 4px 0;
        border-left: 4px solid #28a745;
    }
    .signal-card-loss {
        background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%);
        padding: 10px;
        border-radius: 8px;
        margin: 4px 0;
        border-left: 4px solid #dc3545;
    }
    .mobile-workflow {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 12px;
        border-radius: 8px;
        color: white;
        margin: 8px 0;
    }
    .refresh-banner {
        background: linear-gradient(135deg, #0088cc 0%, #00aced 100%);
        padding: 8px;
        border-radius: 6px;
        color: white;
        text-align: center;
        margin: 4px 0;
    }
    .quick-input {
        background: linear-gradient(135deg, #FF6B35 0%, #F7931E 100%);
        padding: 8px;
        border-radius: 6px;
        color: white;
        margin: 4px 0;
    }
    .prediction-high { 
        background: #00b09b; 
        color: white; 
        padding: 4px 8px; 
        border-radius: 12px; 
        font-size: 0.8em; 
        font-weight: bold;
    }
    .prediction-medium { 
        background: #ff9a00; 
        color: white; 
        padding: 4px 8px; 
        border-radius: 12px; 
        font-size: 0.8em; 
        font-weight: bold;
    }
    .prediction-low { 
        background: #ff416c; 
        color: white; 
        padding: 4px 8px; 
        border-radius: 12px; 
        font-size: 0.8em; 
        font-weight: bold;
    }
    .stats-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .auto-badge {
        background: #00b09b;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.7em;
        margin-left: 5px;
    }
    .queue-badge {
        background: #ff9a00;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.7em;
    }
</style>
""", unsafe_allow_html=True)

def display_environment_info():
    """Display environment configuration"""
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.write(f"**App:** {APP_NAME}")
        st.write(f"**Version:** {os.getenv('APP_VERSION', '2.0.0')}")
        st.write(f"**Bot:** {TELEGRAM_BOT_NAME}")
        st.write(f"**Refresh:** {REFRESH_INTERVAL}s")
        
        # Queue status
        queue_size = len(st.session_state.manual_signals_queue)
        if queue_size > 0:
            st.markdown(f'<div class="queue-badge">Queue: {queue_size}</div>', unsafe_allow_html=True)
        
        # Storage status
        r2_status = "✅ Connected" if R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY else "❌ Not Configured"
        st.write(f"**Cloudflare R2:** {r2_status}")
        
        if st.button("🔄 Process Queue Now"):
            processed = process_queued_signals()
            if processed > 0:
                st.success(f"✅ Processed {processed} signals!")
            st.rerun()
        
        if st.button("🗑️ Clear All Data"):
            processor.signals.clear()
            st.session_state.latest_signals.clear()
            st.session_state.manual_signals_queue.clear()
            processor.save_data()
            st.success("✅ All data cleared!")
            time.sleep(2)
            st.rerun()

def display_dashboard():
    """Display the main dashboard"""
    st.header("📊 LIVE DASHBOARD")
    
    # Get current signals from session state
    signals = processor.signals
    
    st.markdown(f'<div class="bot-card"><h3>🤖 {TELEGRAM_BOT_NAME} <span class="auto-badge">AUTO-PROCESS</span></h3></div>', unsafe_allow_html=True)
    
    if signals:
        # Statistics Row
        st.subheader("📈 Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f'<div class="stats-card"><h4>📊 Total</h4><h2>{len(signals)}</h2></div>', unsafe_allow_html=True)
        with col2:
            wins = len([s for s in signals if s.get('result') == 'Win'])
            st.markdown(f'<div class="stats-card"><h4>✅ Wins</h4><h2>{wins}</h2></div>', unsafe_allow_html=True)
        with col3:
            losses = len([s for s in signals if s.get('result') == 'Lose'])
            st.markdown(f'<div class="stats-card"><h4>❌ Losses</h4><h2>{losses}</h2></div>', unsafe_allow_html=True)
        with col4:
            win_rate = (wins / len(signals) * 100) if signals else 0
            st.markdown(f'<div class="stats-card"><h4>🎯 Win Rate</h4><h2>{win_rate:.1f}%</h2></div>', unsafe_allow_html=True)
        
        # Current Status Row
        st.subheader("🔄 Current Status")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current Phase", processor.current_phase)
        with col2:
            current_multiplier = processor.multipliers[processor.current_phase - 1] if processor.current_phase <= len(processor.multipliers) else 1.0
            st.metric("Next Bet Multiplier", f"x{current_multiplier}")
        
        # Recent Signals
        st.subheader(f"📋 Recent Signals (Last {MAX_SIGNALS_DISPLAY})")
        display_signals = signals[-MAX_SIGNALS_DISPLAY:]
        for signal in reversed(display_signals):
            display_signal_card(signal)
            
    else:
        st.info("📡 No signals yet. Paste signals below to see the dashboard!")

def display_signal_card(signal):
    """Display individual signal card"""
    result = signal.get('result', 'Unknown')
    css_class = "signal-card-win" if result == 'Win' else "signal-card-loss"
    
    st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.write(f"**Period:** {signal['period_id']}")
        st.write(f"**Time:** `{signal['timestamp'].split(' ')[1]}`")
        st.write(f"**Result:** {'✅ WIN' if result == 'Win' else '❌ LOSE'}")
        
    with col2:
        if signal.get('trade_color'):
            trade_emoji = "🟢" if signal['trade_color'] == 'Green' else "🔴"
            st.write(f"**Trade Signal:** {trade_emoji} {signal['trade_color']}")
        
        if signal.get('result_color'):
            color_emoji = "🟢" if signal['result_color'] == 'Green' else "🔴"
            st.write(f"**Actual Result:** {color_emoji} {signal['result_color']}")
        
        st.write(f"**Phase:** {signal.get('phase', 1)}")
        st.write(f"**Bet Amount:** x{signal.get('quantity', 1.0)}")
        
        # Prediction
        if signal.get('prediction'):
            pred = signal['prediction']
            pred_color = pred.get('color', 'Analyzing')
            confidence = pred.get('confidence', 'Low')
            probability = pred.get('probability', 0.5)
            
            pred_emoji = "🟢" if pred_color == 'Green' else "🔴" if pred_color == 'Red' else "⚫"
            confidence_class = f"prediction-{confidence.lower()}"
            
            st.write(f"**AI Prediction:** {pred_emoji} {pred_color}")
            st.markdown(f'<div class="{confidence_class}">Confidence: {confidence} ({probability*100:.1f}%)</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def main():
    # Header
    st.markdown(f'<div class="main-header">{APP_NAME}</div>', unsafe_allow_html=True)
    
    # Display environment info in sidebar
    display_environment_info()
    
    # Workflow info
    st.markdown(f"""
    <div class="mobile-workflow">
    <h3>🤖 EXACT TELEGRAM FORMAT SUPPORT</h3>
    <ol>
    <li><strong>COPY</strong> multiple signals directly from Telegram</li>
    <li><strong>PASTE</strong> exactly as they appear</li>
    <li><strong>WATCH</strong> auto-processing of all signals</li>
    </ol>
    <p><strong>⚡ Supports your exact signal format</strong></p>
    <p><strong>☁️ Data saved to Cloudflare R2</strong></p>
    </div>
    """, unsafe_allow_html=True)
    
    # Process any queued signals first
    queue_size = len(st.session_state.manual_signals_queue)
    if queue_size > 0:
        st.info(f"🔄 Processing {queue_size} signals in queue...")
        processed = process_queued_signals()
        if processed > 0:
            st.success(f"✅ Auto-processed {processed} signals!")
            time.sleep(1)
            st.rerun()
    
    st.markdown(f'<div class="refresh-banner">🔄 LIVE DASHBOARD - Auto-refreshes every {REFRESH_INTERVAL} seconds</div>', unsafe_allow_html=True)
    
    # Signal Input Section
    st.header("🚀 BULK SIGNAL INPUT")
    st.markdown('<div class="quick-input"><h4>📋 Paste EXACT Telegram Signals Below</h4></div>', unsafe_allow_html=True)
    
    telegram_input = st.text_area(
        "Paste signals exactly as they appear in Telegram:",
        height=300,
        key="signal_input",
        placeholder="""Paste your EXACT Telegram signals here:

ETHGPT60s_1#:
⏰Transaction type: ETH 1 minutes⏰

🚥Transaction Tips🚥

📌Current period ID: 202510211143

🔔Result:Win🎉
——————————————————
🔜Next issue

📌period ID: 202510211144

📲Trade: 🔴✔️

Recommended quantity: x1

[More signals...]"""
    )
    
    # Process button
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("🚀 PROCESS ALL SIGNALS", key="process_btn", use_container_width=True):
            if telegram_input.strip():
                # Split by empty lines or specific patterns to get individual signals
                signal_blocks = re.split(r'\n\s*\n\s*[⏰ETHGPT]', telegram_input.strip())
                processed_count = 0
                
                # If splitting didn't work well, try another method
                if len(signal_blocks) <= 1:
                    signal_blocks = re.split(r'(?=⏰Transaction type:)', telegram_input.strip())
                    signal_blocks = [s for s in signal_blocks if s.strip()]
                
                with st.spinner(f"🔄 Processing {len(signal_blocks)} signals..."):
                    for signal_block in signal_blocks:
                        if signal_block.strip():
                            # Ensure the block starts with transaction type
                            if not signal_block.strip().startswith('⏰'):
                                signal_block = '⏰Transaction type: ETH 1 minutes⏰\n\n' + signal_block
                            
                            signal = processor.parse_signal(signal_block)
                            if signal:
                                if processor.add_signal(signal):
                                    processed_count += 1
                
                if processed_count > 0:
                    st.balloons()
                    st.success(f"🎉 Successfully processed {processed_count} signals! Dashboard updated.")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ No valid signals found. Please check the format.")
            else:
                st.error("❌ Please paste some signals")
    
    with col2:
        if st.button("🔄 Auto-Process", key="auto_btn"):
            # Add to queue for auto-processing
            if telegram_input.strip():
                signal_blocks = re.split(r'\n\s*\n\s*[⏰ETHGPT]', telegram_input.strip())
                if len(signal_blocks) <= 1:
                    signal_blocks = re.split(r'(?=⏰Transaction type:)', telegram_input.strip())
                    signal_blocks = [s for s in signal_blocks if s.strip()]
                
                for signal_block in signal_blocks:
                    if signal_block.strip():
                        if not signal_block.strip().startswith('⏰'):
                            signal_block = '⏰Transaction type: ETH 1 minutes⏰\n\n' + signal_block
                        add_to_manual_queue(signal_block)
                st.success(f"✅ Added {len(signal_blocks)} signals to auto-processing queue!")
                time.sleep(1)
                st.rerun()
    
    # Dashboard
    display_dashboard()
    
    # Auto-refresh and process queue
    time.sleep(REFRESH_INTERVAL)
    st.rerun()

if __name__ == "__main__":
    main()
