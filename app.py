import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- ASWATH DAMODARAN - GINSU DEĞERLEME MOTORU V2.0 ---

st.set_page_config(page_title="Damodaran Değerleme Motoru", layout="wide")

def get_base_data(ticker_symbol):
    if not ticker_symbol.endswith(".IS") and not "." in ticker_symbol:
        ticker_symbol += ".IS"
    
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        # Finansalları Çek
        income_stmt = ticker.financials
        balance_sheet = ticker.balance_sheet
        curr_data = ticker.fast_info
        
        exchange_rate = yf.Ticker("USDTRY=X").fast_info['last_price']
        
        # Gelir Tablosu Kalemleri (USD)
        revenue = income_stmt.loc['Total Revenue'].iloc[0] / exchange_rate
        
        # Esnek EBIT
        if 'EBIT' in income_stmt.index:
            ebit = income_stmt.loc['EBIT'].iloc[0] / exchange_rate
        elif 'Operating Income' in income_stmt.index:
            ebit = income_stmt.loc['Operating Income'].iloc[0] / exchange_rate
        elif 'Pretax Income' in income_stmt.index:
            ebit = income_stmt.loc['Pretax Income'].iloc[0] / exchange_rate
        else:
            ebit = revenue * 0.10 # Varsayılan %10 marj

        current_margin = ebit / revenue if revenue > 0 else 0.10
        
        # Bilanço Kalemleri (USD)
        total_debt = balance_sheet.loc['Total Debt'].iloc[0] / exchange_rate if 'Total Debt' in balance_sheet.index else 0
        cash = balance_sheet.loc['Cash Cash Equivalents And Short Term Investments'].iloc[0] / exchange_rate if 'Cash Cash Equivalents And Short Term Investments' in balance_sheet.index else 0
        
        # Hisse Adedi
        try:
            shares_out = curr_data['shares']
        except:
            shares_out = ticker.info.get('sharesOutstanding', None)
            
        current_price = curr_data['last_price']
        
        return {
            'revenue': revenue, 'ebit': ebit, 'margin': current_margin, 
            'debt': total_debt, 'cash': cash, 'shares': shares_out, 
            'price_try': current_price, 'exchange_rate': exchange_rate
        }
    except Exception as e:
        return str(e)

# --- ARAYÜZ VE HİKAYE GİRİŞİ ---
st.title("Aswath Damodaran - Gerçek DCF (Hikayeden Sayılara)")
st.markdown("Bu motor, **'FCFF Simple Ginsu'** modelinin Python uyarlamasıdır. Şirketin geçmişini değil, **senin geleceğe dair hikayeni** fiyatlar.")

col1, col2 = st.columns([1, 3])

with col1:
    st.header("1. Şirket Seçimi")
    ticker_input = st.text_input("Hisse Kodu:", "THYAO")
    
    if st.button("Verileri Çek"):
        with st.spinner("Bilanço getiriliyor..."):
            data = get_base_data(ticker_input)
            if isinstance(data, str):
                st.error(f"Veri çekme hatası: {data}")
            else:
                st.session_state['base_data'] = data
                st.success("Veriler başarıyla çekildi!")

if 'base_data' in st.session_state:
    data = st.session_state['base_data']
    
    st.write("---")
    st.header("2. Hikayeni Yarat (Değerleme Varsayımları)")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.subheader("Büyüme & Kârlılık")
        # Gerçek marjı göster ve hedef iste
        current_margin_pct = data['margin'] * 100
        target_margin = st.slider(f"Hedef Faaliyet Marjı (10. Yıl) - (Mevcut: %{current_margin_pct:.1f})", min_value=-20.0, max_value=50.0, value=float(max(5.0, current_margin_pct)), step=0.5) / 100
        
        revenue_growth = st.slider("İlk 5 Yıl Yıllık Gelir Büyümesi (%)", min_value=-10.0, max_value=100.0, value=15.0, step=1.0) / 100
        
    with col_b:
        st.subheader("Yatırım & Verimlilik")
        st.markdown("*1$ Ciro artışı için kaç $ yatırım (CapEx + İşletme Ser.) gerekiyor?*")
        sales_to_capital = st.slider("Satışlar / Sermaye Oranı", min_value=0.1, max_value=5.0, value=1.5, step=0.1)
        tax_rate = st.number_input("Efektif Vergi Oranı (%)", value=25.0) / 100

    with col_c:
        st.subheader("Risk & Sermaye Maliyeti")
        wacc = st.slider("Sermaye Maliyeti (WACC) (%) - İlk 5 Yıl", min_value=5.0, max_value=25.0, value=10.0, step=0.5) / 100
        risk_free_rate = 0.042 # Sabit 10Y ABD Tahvili (4.2%)
        st.info(f"Sonsuz Büyüme (Uç Değer) Risksiz Orana (%4.20) sabitlenmiştir. (Damodaran Kuralı)")

    # --- HESAPLAMA MOTORU (GERÇEK DCF) ---
    if st.button("İçsel Değeri Hesapla"):
        revenues = [data['revenue']]
        ebits = []
        fcffs = []
        discount_factors = []
        
        current_wacc = wacc
        terminal_wacc = risk_free_rate + 0.045 # Olgun şirket varsayımı (Risk Free + US ERP)
        
        # 10 Yıllık Projeksiyon
        for year in range(1, 11):
            # Büyüme (İlk 5 yıl sabit, sonra risksiz orana düşer)
            if year <= 5:
                g = revenue_growth
            else:
                g = revenue_growth - (revenue_growth - risk_free_rate) * ((year - 5) / 5)
                
            rev_next = revenues[-1] * (1 + g)
            revenues.append(rev_next)
            
            # Marj (Mevcuttan hedefe 10 yılda doğrusal yakınsama)
            margin_next = data['margin'] + (target_margin - data['margin']) * (year / 10)
            ebit_next = rev_next * margin_next
            ebits.append(ebit_next)
            
            # Yeniden Yatırım İhtiyacı (Reinvestment) = Cirodaki Artış / Sales_to_Capital
            reinvestment = (rev_next - revenues[-2]) / sales_to_capital
            
            # Serbest Nakit Akışı (FCFF)
            fcff = (ebit_next * (1 - tax_rate)) - reinvestment
            fcffs.append(fcff)
            
            # İskonto Faktörü (WACC kademeli olarak Terminal WACC'a düşer)
            if year > 5:
                current_wacc = current_wacc - (current_wacc - terminal_wacc) / 5
            
            df = 1 / ((1 + current_wacc) ** year)
            discount_factors.append(df)

        # Uç Değer (Terminal Value) Hesaplaması (Doğru Formül)
        terminal_revenue = revenues[-1] * (1 + risk_free_rate)
        terminal_ebit = terminal_revenue * target_margin
        terminal_nopat = terminal_ebit * (1 - tax_rate)
        
        # Olgun şirkette yeniden yatırım = Büyüme / ROIC (Target ROIC = Terminal WACC varsayımı)
        terminal_reinvestment = terminal_nopat * (risk_free_rate / terminal_wacc)
        terminal_fcff = terminal_nopat - terminal_reinvestment
        
        terminal_value = terminal_fcff / (terminal_wacc - risk_free_rate)
        
        # Bugüne İndirgeme
        pv_of_fcff = sum([fcff * df for fcff, df in zip(fcffs, discount_factors)])
        pv_of_terminal_value = terminal_value * discount_factors[-1]
        
        operating_asset_value = pv_of_fcff + pv_of_terminal_value
        
        # Özkaynak Değeri
        equity_value_usd = operating_asset_value - data['debt'] + data['cash']
        value_per_share_usd = equity_value_usd / data['shares']
        value_per_share_try = value_per_share_usd * data['exchange_rate']
        
        # SONUÇ EKRANI
        st.write("---")
        st.header("3. Değerleme Sonucu")
        
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric("Senin İçsel Değerin", f"{value_per_share_try:.2f} TL")
        res_col2.metric("Güncel Piyasa Fiyatı", f"{data['price_try']:.2f} TL")
        
        upside = (value_per_share_try / data['price_try']) - 1
        res_col3.metric("Potansiyel Getiri", f"%{upside*100:.2f}", delta=f"%{upside*100:.2f}")
        
        # Projeksiyon Tablosu Gösterimi
        st.subheader("10 Yıllık Nakit Akışı Projeksiyonu (USD)")
        proj_df = pd.DataFrame({
            "Yıl": range(1, 11),
            "Ciro": revenues[1:],
            "Faaliyet Karı (EBIT)": ebits,
            "Nakit Akışı (FCFF)": fcffs,
        })
        # Formatlama
        proj_df["Ciro"] = proj_df["Ciro"].map("{:,.0f}".format)
        proj_df["Faaliyet Karı (EBIT)"] = proj_df["Faaliyet Karı (EBIT)"].map("{:,.0f}".format)
        proj_df["Nakit Akışı (FCFF)"] = proj_df["Nakit Akışı (FCFF)"].map("{:,.0f}".format)
        
        st.dataframe(proj_df.set_index("Yıl").T)
        
        st.caption("Not: Bütün projeksiyonlar dolar (USD) bazında yapılmış, en son adımda güncel kur ile TL'ye çevrilmiştir.")
