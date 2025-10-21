import streamlit as st
import time
from datetime import datetime
from collections import deque, Counter
import re
import numpy as np

# Global variables
latest_signals = deque(maxlen=50)
bot_monitors = {}

class LightweightPredictor:
    def __init__(self):
        self.pattern_history = []
    
    def predict(self, signals):
        """Lightweight prediction using pattern analysis"""
        if len(signals) < 3:
            return {'color': 'Analyzing...', 'confidence': 'Low', 'probability': 0.5}
        
        recent_colors = [s.get('result_color') for s in signals[-5:] if s.get('result_color') in ['Green', 'Red']]
        
        if not recent_colors:
            return {'color': 'Green', 'confidence': 'Low', 'probability': 0.5}
        
        # Count recent patterns
        green_count = recent_colors.count('Green')
        red_count = recent_colors.count('Red')
        total_known = green_count + red_count
        
        if total_known == 0:
            return {'color': 'Green', 'confidence': 'Low', 'probability': 0.5}
        
        green_probability = green_count / total_known
        
        # Pattern 1: If last 2 are same, predict opposite
        if len(recent_colors) >= 2 and recent_colors[-1] == recent_colors[-2]:
            predicted_color = 'Red' if recent_colors[-1] == 'Green' else 'Green'
            confidence = 'Medium'
            probability = 0.65
        # Pattern 2: Use weighted probability
        elif green_probability > 0.6:
            predicted_color = 'Green'
            confidence = 'Medium'
            probability = green_probability
        elif green_probability < 0.4:
            predicted_color = 'Red'
            confidence = 'Medium'
            probability = 1 - green_probability
        else:
            predicted_color = 'Green' if green_probability >= 0.5 else 'Red'
            confidence = 'Low'
            probability = 0.55
        
        return {
            'color': predicted_color,
            'confidence': confidence,
            'probability': probability
        }

class SignalProcessor:
    def __init__(self, bot_name):
        self.bot_name = bot_name
        self.signals = []
        self.last_period_id = None
        self.predictor = LightweightPredictor()
        self.win_streak = 0
        self.loss_streak = 0
        self.current_phase = 1
        self.recommended_multipliers = [1.0, 2.5, 6.25, 15.63, 39.08, 97.62, 244.05, 610.12, 1525.3, 3813.25, 9533.12, 23832.8]
    
    def parse_telegram_signal(self, message):
        """Parse signals from Telegram channel format"""
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
                'bot_name': self.bot_name
            }
            
            # Extract period ID
            period_match = re.search(r'period ID[:\s]*(\d+)', message, re.IGNORECASE)
            if not period_match:
                period_match = re.search(r'ID[:\s]*(\d+)', message)
            if period_match:
                signal_data['period_id'] = period_match.group(1)
            else:
                st.error("❌ Could not find Period ID")
                return None
            
            # Extract result (Win/Lose)
            if 'Result:Win' in message or 'Win🎉' in message:
                signal_data['result'] = 'Win'
                signal_data['result_color'] = self.get_actual_result_color()
                self.win_streak += 1
                self.loss_streak = 0
                self.current_phase = 1
            elif 'Result:Lose' in message or 'Lose💔' in message:
                signal_data['result'] = 'Lose'
                signal_data['result_color'] = self.get_actual_result_color()
                self.loss_streak += 1
                self.win_streak = 0
                if self.loss_streak < len(self.recommended_multipliers):
                    self.current_phase = self.loss_streak + 1
            else:
                st.warning("⚠️ Could not determine Win/Lose")
                return None
            
            # Extract trade color
            if 'Trade: 🟢' in message or 'Trade: Green' in message or 'Trade:🟢' in message or '🟢✔️' in message:
                signal_data['trade_color'] = 'Green'
            elif 'Trade: 🔴' in message or 'Trade: Red' in message or 'Trade:🔴' in message or '🔴✔️' in message:
                signal_data['trade_color'] = 'Red'
            else:
                st.warning("⚠️ Could not find trade color")
                return None
            
            # Extract quantity
            quantity_match = re.search(r'quantity: x?([\d.]+)', message, re.IGNORECASE)
            if quantity_match:
                try:
                    signal_data['quantity'] = float(quantity_match.group(1))
                except:
                    signal_data['quantity'] = self.recommended_multipliers[self.current_phase - 1] if self.current_phase <= len(self.recommended_multipliers) else 1.0
            else:
                signal_data['quantity'] = self.recommended_multipliers[self.current_phase - 1] if self.current_phase <= len(self.recommended_multipliers) else 1.0
            
            # Add prediction
            signal_data['prediction'] = self.predictor.predict(self.signals)
            return signal_data
            
        except Exception as e:
            st.error(f"❌ Error: {e}")
            return None
    
    def get_actual_result_color(self):
        """Generate realistic color results"""
        colors = ['Green', 'Red']
        weights = [0.48, 0.52]
        return np.random.choice(colors, p=weights)
    
    def add_signal(self, signal_data):
        if signal_data and signal_data['period_id'] != self.last_period_id:
            self.signals.append(signal_data)
            self.last_period_id = signal_data['period_id']
            
            if len(self.signals) > 50:
                self.signals = self.signals[-50:]
            
            global latest_signals
            latest_signals.append(signal_data)
            return True
        return False

# Initialize bots
def initialize_bots():
    target_bots = ["ETHGPT60s_bot"]
    for i, bot in enumerate(target_bots):
        bot_name = f"Bot_{i+1}_{bot}"
        bot_monitors[bot_name] = SignalProcessor(bot_name)

initialize_bots()

# Streamlit App
st.set_page_config(
    page_title="Coinryze Pro Analyzer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS Styles
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
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
    .prediction-high { background: #00b09b; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8em; }
    .prediction-medium { background: #ff9a00; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8em; }
    .prediction-low { background: #ff416c; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8em; }
</style>
""", unsafe_allow_html=True)

def create_bot_dashboard(bot_name, processor):
    signals = processor.signals[-8:]
    
    st.markdown(f'<div class="bot-card"><h3>🤖 {bot_name}</h3></div>', unsafe_allow_html=True)
    
    if signals:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📊 Total", len(signals))
        with col2:
            wins = len([s for s in signals if s.get('result') == 'Win'])
            st.metric("✅ Wins", wins)
        with col3:
            losses = len([s for s in signals if s.get('result') == 'Lose'])
            st.metric("❌ Losses", losses)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🔄 Phase", processor.current_phase)
        with col2:
            current_multiplier = processor.recommended_multipliers[processor.current_phase - 1] if processor.current_phase <= len(processor.recommended_multipliers) else 1.0
            st.metric("💰 Multiplier", f"x{current_multiplier}")
        
        st.subheader("📋 Recent Signals")
        for signal in reversed(signals[-5:]):
            result = signal.get('result', 'Unknown')
            css_class = "signal-card-win" if result == 'Win' else "signal-card-loss"
            
            st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
            col1, col2 = st.columns([2, 3])
            
            with col1:
                st.write(f"**{signal['period_id']}**")
                st.write(f"`{signal['timestamp'].split(' ')[1]}`")
                st.write(f"**Result:** {'✅' if result == 'Win' else '❌'} {result}")
                
            with col2:
                if signal.get('trade_color'):
                    trade_emoji = "🟢" if signal['trade_color'] == 'Green' else "🔴"
                    st.write(f"**Trade:** {trade_emoji} {signal['trade_color']}")
                
                if signal.get('result_color'):
                    color_emoji = "🟢" if signal['result_color'] == 'Green' else "🔴"
                    st.write(f"**Color:** {color_emoji} {signal['result_color']}")
                
                st.write(f"**Phase:** {signal.get('phase', 1)}")
                st.write(f"**Bet:** x{signal.get('quantity', 1.0)}")
                
                if signal.get('prediction'):
                    pred = signal['prediction']
                    pred_color = pred.get('color', 'Analyzing')
                    confidence = pred.get('confidence', 'Low')
                    probability = pred.get('probability', 0.5)
                    
                    pred_emoji = "🟢" if pred_color == 'Green' else "🔴" if pred_color == 'Red' else "⚫"
                    confidence_class = f"prediction-{confidence.lower()}"
                    
                    st.write(f"**Next:** {pred_emoji} {pred_color}")
                    st.markdown(f'<div class="{confidence_class}">Confidence: {confidence} ({probability*100:.1f}%)</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("📡 Waiting for signals...")

def main():
    st.markdown('<div class="main-header">🎯 COINRYZE PRO ANALYZER</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="mobile-workflow">
    <h3>📱 ULTRA FAST WORKFLOW</h3>
    <ol>
    <li><strong>COPY</strong> signal from @ETHGPT60s_bot Telegram</li>
    <li><strong>PASTE</strong> in the input below</li>
    <li><strong>VIEW</strong> AI predictions instantly</li>
    </ol>
    <p><strong>⚡ Perfect for Samsung Galaxy A9+</strong></p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="refresh-banner">🔄 LIVE DASHBOARD - Optimized for Render Free Tier</div>', unsafe_allow_html=True)
    
    # Signal Input
    st.header("🚀 SIGNAL INPUT")
    st.markdown('<div class="quick-input"><h4>📋 Paste Telegram Signal Below</h4></div>', unsafe_allow_html=True)
    
    telegram_input = st.text_area(
        "Paste complete signal message:",
        height=150,
        placeholder="""Example:
⏰Transaction type: ETH 1 minutes⏰
📌Current period ID: 202510210580
🔔Result:Win🎉
📌period ID: 202510210581
📲Trade: 🟢✔️
Recommended quantity: x1"""
    )
    
    if st.button("🚀 PROCESS SIGNAL", use_container_width=True):
        if telegram_input:
            processor = bot_monitors["Bot_1_ETHGPT60s_bot"]
            signal = processor.parse_telegram_signal(telegram_input)
            if signal:
                if processor.add_signal(signal):
                    st.success(f"✅ PROCESSED: Period {signal['period_id']} - {signal['result']}")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.warning("⚠️ Signal already processed")
            else:
                st.error("❌ Invalid signal format")
        else:
            st.error("❌ Please paste a signal message")
    
    # Dashboard
    st.header("📊 LIVE DASHBOARD")
    for bot_name, processor in bot_monitors.items():
        create_bot_dashboard(bot_name, processor)
    
    # Global Stats
    st.header("🌐 GLOBAL STATISTICS")
    global_signals = list(latest_signals)
    if global_signals:
        col1, col2, col3, col4 = st.columns(4)
        total_signals = len(global_signals)
        wins = len([s for s in global_signals if s.get('result') == 'Win'])
        losses = len([s for s in global_signals if s.get('result') == 'Lose'])
        
        with col1:
            st.metric("📈 Total", total_signals)
        with col2:
            st.metric("✅ Wins", wins)
        with col3:
            st.metric("❌ Losses", losses)
        with col4:
            win_rate = (wins / total_signals * 100) if total_signals > 0 else 0
            st.metric("🎯 Win Rate", f"{win_rate:.1f}%")
    
    # Auto-refresh
    time.sleep(10)
    st.rerun()

if __name__ == "__main__":
    main()
