import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- ASWATH DAMODARAN - OTO-PİLOT DEĞERLEME MOTORU V3.0 ---
# "Senin yerine Damodaran düşünür"

st.set_page_config(page_title="Damodaran Değerleme Motoru", layout="wide")

# Makro Veriler (Sabit Damodaran Kuralları)
ERP_US = 0.045
CRP_TURKEY = 0.035
RISK_FREE_USD = 0.042

def get_base_data(ticker_symbol):
    if not ticker_symbol.endswith(".IS") and not "." in ticker_symbol:
        ticker_symbol += ".IS"
    
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        income_stmt = ticker.financials
        balance_sheet = ticker.balance_sheet
        cash_flow = ticker.cashflow
        curr_data = ticker.fast_info
        
        exchange_rate = yf.Ticker("USDTRY=X").fast_info['last_price']
        
        # Ciro ve Kar (Esnek Arama)
        revenue = income_stmt.loc['Total Revenue'].iloc[0] / exchange_rate
        
        if 'EBIT' in income_stmt.index:
            ebit = income_stmt.loc['EBIT'].iloc[0] / exchange_rate
        elif 'Operating Income' in income_stmt.index:
            ebit = income_stmt.loc['Operating Income'].iloc[0] / exchange_rate
        elif 'Pretax Income' in income_stmt.index:
            ebit = income_stmt.loc['Pretax Income'].iloc[0] / exchange_rate
        else:
            ebit = revenue * 0.10 # Bulunamazsa sektör ortalaması varsayımı
            
        current_margin = ebit / revenue if revenue > 0 else 0.10
        
        # Bilanço
        total_debt = balance_sheet.loc['Total Debt'].iloc[0] / exchange_rate if 'Total Debt' in balance_sheet.index else 0
        cash = balance_sheet.loc['Cash Cash Equivalents And Short Term Investments'].iloc[0] / exchange_rate if 'Cash Cash Equivalents And Short Term Investments' in balance_sheet.index else 0
        
        try:
            shares_out = curr_data['shares']
        except:
            shares_out = ticker.info.get('sharesOutstanding', None)
            
        current_price = curr_data['last_price']
        
        # Faiz Karşılama ve Sentetik Rating (Borç Maliyeti İçin)
        try:
            interest_expense = abs(income_stmt.loc['Interest Expense'].iloc[0] / exchange_rate)
        except:
            interest_expense = 0
            
        interest_coverage = ebit / interest_expense if interest_expense > 0 else 100
        default_spread = 0.015 if interest_coverage > 8.5 else 0.05
        
        return {
            'ticker': ticker_symbol, 'revenue': revenue, 'ebit': ebit, 
            'margin': current_margin, 'debt': total_debt, 'cash': cash, 
            'shares': shares_out, 'price_try': current_price, 
            'exchange_rate': exchange_rate, 'default_spread': default_spread
        }
    except Exception as e:
        return str(e)

# --- ARAYÜZ ---
st.title("Aswath Damodaran - Oto-Pilot DCF Motoru")
st.markdown("Sistem şirketin mevcut durumunu analiz eder ve **Damodaran'ın ortalamaya dönüş (mean-reversion) kurallarına göre** geleceği otomatik kurgular.")

col1, col2 = st.columns([1, 3])

with col1:
    st.header("1. Şirket Seçimi")
    ticker_input = st.text_input("Hisse Kodu:", "THYAO")
    
    if st.button("Damodaran Beynini Çalıştır"):
        with st.spinner("Şirket inceleniyor ve Damodaran kuralları uygulanıyor..."):
            data = get_base_data(ticker_input)
            if isinstance(data, str):
                st.error(f"Veri çekme hatası: {data}")
            else:
                st.session_state['base_data'] = data
                st.success("Otomatik Hikaye Yazıldı!")

if 'base_data' in st.session_state:
    data = st.session_state['base_data']
    
    # -- DAMODARAN OTOMATİK HİKAYE YAZILIMI (AI LOGIC) --
    
    # 1. Otomatik Marj Kuralı
    # Zarar ediyorsa %10 küresel ortalamaya döner, %25'ten fazlaysa rekabetle %20'ye düşer, normalse kendi marjını korur.
    current_margin_pct = data['margin'] * 100
    if current_margin_pct < 0:
        auto_target_margin = 10.0
    elif current_margin_pct > 25:
        auto_target_margin = current_margin_pct - 5.0
    else:
        auto_target_margin = max(5.0, current_margin_pct) # En az %5 marj
        
    # 2. Otomatik Büyüme Kuralı
    # Yüksek marjlı, karlı şirket daha hızlı büyür. Normal şirket Risksiz oran + %5 büyür.
    auto_growth = (RISK_FREE_USD * 100) + 5.0
    
    # 3. Otomatik WACC (Sermaye Maliyeti)
    beta = 1.10
    cost_of_equity = RISK_FREE_USD + beta * (ERP_US + (CRP_TURKEY if ".IS" in data['ticker'] else 0))
    pre_tax_cost_of_debt = RISK_FREE_USD + data['default_spread'] + (CRP_TURKEY if ".IS" in data['ticker'] else 0)
    tax_rate_assumed = 0.25
    market_cap = (data['price_try'] * data['shares']) / data['exchange_rate']
    auto_wacc = (cost_of_equity * (market_cap/(market_cap+data['debt']))) + (pre_tax_cost_of_debt * (1-tax_rate_assumed) * (data['debt']/(market_cap+data['debt'])))
    
    st.write("---")
    st.header("2. Damodaran'ın Otomatik Varsayımları")
    st.info("Bu ayarlar şirketin bilançosuna bakılarak 'Ortalamaya Dönüş' (Mean Reversion) kurallarıyla otomatik dolduruldu. İstersen müdahale edebilirsin.")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        target_margin = st.slider(f"Hedef Marj (Mevcut: %{current_margin_pct:.1f})", min_value=-10.0, max_value=50.0, value=float(auto_target_margin), step=0.5) / 100
        revenue_growth = st.slider("İlk 5 Yıl Ciro Büyümesi (%)", min_value=0.0, max_value=50.0, value=float(auto_growth), step=1.0) / 100
        
    with col_b:
        sales_to_capital = st.slider("Satışlar/Sermaye (Global Ort: 1.5)", min_value=0.5, max_value=3.0, value=1.5, step=0.1)
        tax_rate = st.number_input("Vergi Oranı (%)", value=25.0) / 100

    with col_c:
        wacc = st.slider("Sermaye Maliyeti (WACC) (%)", min_value=5.0, max_value=25.0, value=float(auto_wacc*100), step=0.5) / 100
        st.write(f"**Uç Değer Büyümesi:** %{RISK_FREE_USD*100:.2f} (Risksiz Orana Sabitlendi)")

    # --- HESAPLAMA MOTORU ---
    revenues = [data['revenue']]
    ebits = []
    fcffs = []
    discount_factors = []
    
    current_wacc = wacc
    terminal_wacc = RISK_FREE_USD + 0.045
    
    for year in range(1, 11):
        if year <= 5:
            g = revenue_growth
        else:
            g = revenue_growth - (revenue_growth - RISK_FREE_USD) * ((year - 5) / 5)
            
        rev_next = revenues[-1] * (1 + g)
        revenues.append(rev_next)
        
        margin_next = data['margin'] + (target_margin - data['margin']) * (year / 10)
        ebit_next = rev_next * margin_next
        ebits.append(ebit_next)
        
        reinvestment = (rev_next - revenues[-2]) / sales_to_capital
        fcff = (ebit_next * (1 - tax_rate)) - reinvestment
        fcffs.append(fcff)
        
        if year > 5:
            current_wacc = current_wacc - (current_wacc - terminal_wacc) / 5
        
        df = 1 / ((1 + current_wacc) ** year)
        discount_factors.append(df)

    terminal_revenue = revenues[-1] * (1 + RISK_FREE_USD)
    terminal_ebit = terminal_revenue * target_margin
    terminal_nopat = terminal_ebit * (1 - tax_rate)
    
    terminal_reinvestment = terminal_nopat * (RISK_FREE_USD / terminal_wacc)
    terminal_fcff = terminal_nopat - terminal_reinvestment
    terminal_value = terminal_fcff / (terminal_wacc - RISK_FREE_USD)
    
    pv_of_fcff = sum([fcff * df for fcff, df in zip(fcffs, discount_factors)])
    pv_of_terminal_value = terminal_value * discount_factors[-1]
    
    operating_asset_value = pv_of_fcff + pv_of_terminal_value
    equity_value_usd = operating_asset_value - data['debt'] + data['cash']
    
    value_per_share_usd = equity_value_usd / data['shares']
    value_per_share_try = value_per_share_usd * data['exchange_rate']
    
    # SONUÇ EKRANI
    st.write("---")
    st.header("3. Değerleme Sonucu")
    
    res_col1, res_col2, res_col3 = st.columns(3)
    res_col1.metric("Oto-Pilot İçsel Değer", f"{value_per_share_try:.2f} TL")
    res_col2.metric("Güncel Piyasa Fiyatı", f"{data['price_try']:.2f} TL")
    
    upside = (value_per_share_try / data['price_try']) - 1
    res_col3.metric("Potansiyel Getiri", f"%{upside*100:.2f}", delta=f"%{upside*100:.2f}")
