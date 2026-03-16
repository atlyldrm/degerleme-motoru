import streamlit as st
import yfinance as yf
import pandas as pd

# Aswath Damodaran tarzı basit DCF motoru
# Makro Veriler (Şimdilik sabit, daha sonra API ile otomatik yapılabilir)
ERP_US = 0.045
CRP_TURKEY = 0.035
RISK_FREE_USD = 0.042

def get_valuation(ticker_symbol):
    # Türkiye hisseleri için .IS takısını otomatik ekle
    if not ticker_symbol.endswith(".IS") and not "." in ticker_symbol:
        ticker_symbol += ".IS"
    
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        # Yahoo Finance'ten finansalları çek
        income_stmt = ticker.financials
        balance_sheet = ticker.balance_sheet
        cash_flow = ticker.cashflow
        curr_data = ticker.fast_info
        
        # Kur Dönüşümü (TRY -> USD) - Tutarlılık Kuralı
        exchange_rate = yf.Ticker("USDTRY=X").fast_info['last_price']
        
        # EBIT'i bulmak için esnek arama (Veri sağlayıcı etiketleme hatalarını önler)
        if 'EBIT' in income_stmt.index:
            ebit = income_stmt.loc['EBIT'].iloc[0] / exchange_rate
        elif 'Operating Income' in income_stmt.index:
            ebit = income_stmt.loc['Operating Income'].iloc[0] / exchange_rate
        elif 'Pretax Income' in income_stmt.index:
            ebit = income_stmt.loc['Pretax Income'].iloc[0] / exchange_rate
        else:
            raise ValueError("Gelir tablosunda faaliyet karı kalemi bulunamadı!")
            
        # Faiz gideri yoksa veya net faiz geliri varsa hata vermemesi için
        try:
            interest_expense = abs(income_stmt.loc['Interest Expense'].iloc[0] / exchange_rate)
        except:
            interest_expense = 0
            
        tax_rate = 0.25 # Türkiye kurumlar vergisi varsayımı
        capex = abs(cash_flow.loc['Capital Expenditure'].iloc[0]) / exchange_rate
        depreciation = cash_flow.loc['Depreciation And Amortization'].iloc[0] / exchange_rate
        change_wc = 0.02 * ebit # Basitleştirilmiş işletme sermayesi 
        
        # Sermaye Maliyeti (Cost of Capital)
        beta = 1.10 # Otomatize edilene kadar sektör ortalaması varsayımı
        cost_of_equity = RISK_FREE_USD + beta * (ERP_US + (CRP_TURKEY if ".IS" in ticker_symbol else 0))
        
        interest_coverage = ebit / interest_expense if interest_expense > 0 else 100
        default_spread = 0.015 if interest_coverage > 8.5 else 0.05
        pre_tax_cost_of_debt = RISK_FREE_USD + default_spread + (CRP_TURKEY if ".IS" in ticker_symbol else 0)
        
        market_cap = curr_data['market_cap'] / exchange_rate
        total_debt = balance_sheet.loc['Total Debt'].iloc[0] / exchange_rate if 'Total Debt' in balance_sheet.index else 0
        wacc = (cost_of_equity * (market_cap/(market_cap+total_debt))) + (pre_tax_cost_of_debt * (1-tax_rate) * (total_debt/(market_cap+total_debt)))

        # Nakit Akışı Projeksiyonu ve Uç Değer
        fcff_base = (ebit * (1-tax_rate)) - (capex - depreciation + change_wc)
        terminal_growth = RISK_FREE_USD # Büyüme risksiz oranı geçemez kuralı
        terminal_value = (fcff_base * (1 + terminal_growth)) / (wacc - terminal_growth)
        
        # İçsel Değer (Intrinsic Value) Hesabı
        intrinsic_value_firm = (fcff_base / (1 + wacc)) + (terminal_value / (1 + wacc))
        cash = balance_sheet.loc['Cash Cash Equivalents And Short Term Investments'].iloc[0] / exchange_rate if 'Cash Cash Equivalents And Short Term Investments' in balance_sheet.index else 0
        
        intrinsic_value_equity = intrinsic_value_firm - total_debt + cash
        
        # Hisse senedi adedini bulmak için esnek arama
        try:
            shares_out = curr_data['shares']
        except:
            shares_out = ticker.info.get('sharesOutstanding', None)
            
        if not shares_out:
            raise ValueError("Hisse adedi (Shares Outstanding) verisi bulunamadı!")

        value_per_share_usd = intrinsic_value_equity / shares_out
        value_per_share_try = value_per_share_usd * exchange_rate
        
        return value_per_share_try, curr_data['last_price']
    except Exception as e:
        return None, str(e)

# --- STREAMLIT ARAYÜZÜ ---
st.title("Aswath Damodaran - Otomatik Değerleme Motoru")
st.write("Finansalları çeker, kurları ayarlar, risk primini ekler ve İçsel Değeri (Intrinsic Value) bulur.")

ticker_input = st.text_input("Hisse Kodu Girin (Örn: THYAO, EREGL, AAPL)", "THYAO")

if st.button("Değerlemeyi Çalıştır"):
    with st.spinner('Piyasa verileri ve bilançolar çekiliyor... Sabırlı ol, iyi değerleme zaman alır.'):
        val_try, curr_p = get_valuation(ticker_input)
        
        if val_try is None:
            st.error(f"Bir hata oluştu. Şirket bilançosunda eksik kalem olabilir. Detay: {curr_p}")
        else:
            st.success("Hesaplama Tamamlandı!")
            col1, col2, col3 = st.columns(3)
            col1.metric("Hesaplanan İçsel Değer", f"{val
