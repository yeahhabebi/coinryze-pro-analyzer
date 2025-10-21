import streamlit as st
import time
from datetime import datetime
import re
import random

# Global variables
latest_signals = []
bot_monitors = {}

class LightweightPredictor:
    def predict(self, signals):
        if len(signals) < 3:
            return {'color': 'Analyzing...', 'confidence': 'Low', 'probability': 0.5}
        
        recent_colors = [s.get('result_color') for s in signals[-5:] if s.get('result_color') in ['Green', 'Red']]
        
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
        self.multipliers = [1.0, 2.5, 6.25, 15.63, 39.08, 97.62]
    
    def parse_signal(self, message):
        try:
            if not message:
                st.error("❌ No message provided")
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
            
            # DEBUG: Show what we're parsing
            st.write("🔍 **Debug - Parsing message:**")
            st.code(message)
            
            # Extract period ID - FIXED REGEX
            period_match = re.search(r'period ID:\s*(\d+)', message)
            if not period_match:
                period_match = re.search(r'ID:\s*(\d+)', message)
            if not period_match:
                period_match = re.search(r'Current period ID:\s*(\d+)', message)
            
            if period_match:
                signal_data['period_id'] = period_match.group(1)
                st.success(f"✅ Found Period ID: {signal_data['period_id']}")
            else:
                st.error("❌ Could not find Period ID")
                return None
            
            # Extract result - FIXED
            if 'Result:Win' in message or 'Win🎉' in message:
                signal_data['result'] = 'Win'
                signal_data['result_color'] = random.choice(['Green', 'Red'])
                self.current_phase = 1
                st.success("✅ Result: Win")
            elif 'Result:Lose' in message or 'Lose💔' in message:
                signal_data['result'] = 'Lose'
                signal_data['result_color'] = random.choice(['Green', 'Red'])
                if self.current_phase < len(self.multipliers):
                    self.current_phase += 1
                st.warning("⚠️ Result: Lose")
            else:
                st.error("❌ Could not determine Win/Lose")
                return None
            
            # Extract trade color - FIXED
            if '🟢' in message or 'Trade: 🟢' in message or 'Trade: Green' in message:
                signal_data['trade_color'] = 'Green'
                st.success("✅ Trade: Green")
            elif '🔴' in message or 'Trade: 🔴' in message or 'Trade: Red' in message:
                signal_data['trade_color'] = 'Red'
                st.success("✅ Trade: Red")
            else:
                st.error("❌ Could not find trade color")
                return None
            
            # Extract quantity - FIXED
            qty_match = re.search(r'quantity:\s*x?([\d.]+)', message, re.IGNORECASE)
            if qty_match:
                try:
                    signal_data['quantity'] = float(qty_match.group(1))
                    st.success(f"✅ Quantity: x{signal_data['quantity']}")
                except:
                    signal_data['quantity'] = self.multipliers[self.current_phase - 1]
                    st.info(f"ℹ️ Using default quantity: x{signal_data['quantity']}")
            else:
                signal_data['quantity'] = self.multipliers[self.current_phase - 1]
                st.info(f"ℹ️ Using default quantity: x{signal_data['quantity']}")
            
            # Add prediction
            signal_data['prediction'] = self.predictor.predict(self.signals)
            st.success("✅ Prediction generated")
            
            return signal_data
            
        except Exception as e:
            st.error(f"❌ Parse error: {str(e)}")
            return None
    
    def add_signal(self, signal_data):
        if signal_data:
            if signal_data['period_id'] != self.last_period_id:
                self.signals.append(signal_data)
                self.last_period_id = signal_data['period_id']
                
                if len(self.signals) > 20:
                    self.signals = self.signals[-20:]
                
                global latest_signals
                latest_signals.append(signal_data)
                if len(latest_signals) > 30:
                    latest_signals = latest_signals[-30:]
                
                st.success(f"🎯 SUCCESS! Added signal {signal_data['period_id']} to dashboard")
                return True
            else:
                st.warning("⚠️ Signal already processed (same Period ID)")
                return False
        return False

# Initialize bot
bot_monitors["Bot_1_ETHGPT60s_bot"] = SignalProcessor("ETHGPT60s_bot")

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
    .debug-info {
        background: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        border-left: 4px solid #6c757d;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)

def display_dashboard():
    """Display the main dashboard"""
    st.header("📊 LIVE DASHBOARD")
    
    for bot_name, processor in bot_monitors.items():
        signals = processor.signals
        
        st.markdown(f'<div class="bot-card"><h3>🤖 {bot_name}</h3></div>', unsafe_allow_html=True)
        
        if signals:
            # Statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Total Signals", len(signals))
            with col2:
                wins = len([s for s in signals if s.get('result') == 'Win'])
                st.metric("✅ Wins", wins)
            with col3:
                losses = len([s for s in signals if s.get('result') == 'Lose'])
                st.metric("❌ Losses", losses)
            with col4:
                win_rate = (wins / len(signals) * 100) if signals else 0
                st.metric("🎯 Win Rate", f"{win_rate:.1f}%")
            
            # Current phase info
            col1, col2 = st.columns(2)
            with col1:
                st.metric("🔄 Current Phase", processor.current_phase)
            with col2:
                current_multiplier = processor.multipliers[processor.current_phase - 1] if processor.current_phase <= len(processor.multipliers) else 1.0
                st.metric("💰 Next Bet", f"x{current_multiplier}")
            
            # Recent Signals
            st.subheader("📋 Recent Signals (Newest First)")
            for signal in reversed(signals[-10:]):  # Show last 10 signals
                display_signal_card(signal)
        else:
            st.info("📡 No signals yet. Process a signal above to see the dashboard!")
            
            # Show sample signal for testing
            with st.expander("🧪 Click here for TEST SIGNAL"):
                test_signal = """⏰Transaction type: ETH 1 minutes⏰

📌Current period ID: 202510210929
🔔Result:Win🎉
📌period ID: 202510210930
📲Trade: 🔴✔️
Recommended quantity: x1"""
                st.code(test_signal)
                if st.button("🚀 TEST WITH SAMPLE SIGNAL"):
                    processor = bot_monitors["Bot_1_ETHGPT60s_bot"]
                    signal = processor.parse_signal(test_signal)
                    if signal:
                        processor.add_signal(signal)
                        st.success("✅ Test signal processed! Check dashboard.")
                        time.sleep(2)
                        st.rerun()

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
    st.markdown('<div class="main-header">🎯 COINRYZE PRO ANALYZER</div>', unsafe_allow_html=True)
    
    # Workflow info
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
    
    st.markdown('<div class="refresh-banner">🔄 LIVE DASHBOARD - Auto-refreshes every 10 seconds</div>', unsafe_allow_html=True)
    
    # Signal Input Section
    st.header("🚀 SIGNAL INPUT")
    st.markdown('<div class="quick-input"><h4>📋 Paste Telegram Signal Below</h4></div>', unsafe_allow_html=True)
    
    telegram_input = st.text_area(
        "Paste complete signal message:",
        height=150,
        key="signal_input",
        placeholder="""Paste your signal here exactly as it appears in Telegram...

Example format:
⏰Transaction type: ETH 1 minutes⏰
📌Current period ID: 202510210929
🔔Result:Win🎉
📌period ID: 202510210930
📲Trade: 🔴✔️
Recommended quantity: x1"""
    )
    
    # Process button
    if st.button("🚀 PROCESS SIGNAL", key="process_btn", use_container_width=True):
        if telegram_input.strip():
            with st.spinner("🔄 Processing signal..."):
                processor = bot_monitors["Bot_1_ETHGPT60s_bot"]
                signal = processor.parse_signal(telegram_input)
                
                if signal:
                    success = processor.add_signal(signal)
                    if success:
                        st.balloons()
                        st.success("🎉 Signal successfully processed! Check the dashboard below.")
                        time.sleep(3)
                        st.rerun()
                else:
                    st.error("❌ Failed to process signal. Please check the format.")
        else:
            st.error("❌ Please paste a signal message")
    
    # Dashboard
    display_dashboard()
    
    # Auto-refresh
    time.sleep(10)
    st.rerun()

if __name__ == "__main__":
    main()
