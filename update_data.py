import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import logging
import json
import os
import sys
from pykrx import stock
import requests
from bs4 import BeautifulSoup
import openpyxl
import html5lib

# --- ✅ [테스트 설정] ---
# True로 설정하면 각 국가별로 30개 종목만 테스트합니다.
# 실제 운영 시에는 이 값을 False로 바꾸세요.
IS_TEST_MODE = True
TEST_SAMPLE_SIZE = 30
# -------------------------

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 최종 국가별 설정
COUNTRY_CONFIG = {
    'us': { 'name': '미국 (USA)', 'market_cap_filter': '+Large (over $10bln)', 'currency_symbol': '$'},
    'jp': { 'name': '일본 (Japan)', 'currency_symbol': '¥' },
    'hk': { 'name': '홍콩 (Hong Kong)', 'currency_symbol': 'HK$' },
    'kr': { 'name': '한국 (Korea)', 'currency_symbol': '₩', 'top_n': 1500 }
}

def get_stocks_by_country(country_code, config):
    country_name = config['name']
    logging.info(f"'{country_name}'의 전체 종목 목록을 가져오는 중...")
    df = pd.DataFrame()
    try:
        if country_code == 'us':
            logging.info("finvizfinance를 통해 미국 대형주 스크리닝 중...")
            foverview = Overview()
            filters_dict = {'Exchange': ['NASDAQ', 'NYSE'], 'Market Cap.': config['market_cap_filter']}
            foverview.set_filter(filters_dict=filters_dict)
            df = foverview.screener_view(order='Market Cap.', ascend=False)

        elif country_code == 'kr':
            logging.info("pykrx를 통해 KOSPI, KOSDAQ 전 종목 Ticker 가져오는 중...")
            kospi = stock.get_market_ticker_list(market="KOSPI")
            kosdaq = stock.get_market_ticker_list(market="KOSDAQ")
            df['Ticker'] = [f"{ticker}.KS" for ticker in kospi] + [f"{ticker}.KQ" for ticker in kosdaq]

        elif country_code == 'jp':
            logging.info("일본거래소(JPX) 공식 엑셀 파일 다운로드 중...")
            landing_page_url = "https://www.jpx.co.jp/english/markets/statistics-equities/misc/01.html"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(landing_page_url, headers=headers)
            soup = BeautifulSoup(response.content, 'lxml')
            excel_link = soup.find('a', href=lambda href: href and (href.endswith('.xls') or href.endswith('.xlsx')))
            if not excel_link: raise ValueError("JPX 엑셀 링크 찾기 실패")
            file_url = "https://www.jpx.co.jp" + excel_link['href']
            
            df_jpx = pd.read_excel(file_url, header=0)
            df_jpx.columns = df_jpx.columns.str.strip()
            df_filtered = df_jpx[~df_jpx['Section/Products'].str.contains('ETFs/ ETNs|REITs|Pro Market', na=False)]
            df['Ticker'] = df_filtered['Local Code'].astype(str) + '.T'
        
        elif country_code == 'hk':
            logging.info("Wikipedia에서 홍콩 증권거래소 종목 목록 스크래핑 중...")
            url = "https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_Hong_Kong_Stock_Exchange"
            tables = pd.read_html(url)
            df_hk = tables[0]
            # 컬럼 이름이 'Stock Code' 또는 'Ticker'일 수 있으므로 유연하게 처리
            ticker_col = 'Stock Code' if 'Stock Code' in df_hk.columns else 'Ticker'
            df['Ticker'] = df_hk[ticker_col].astype(str).str.zfill(4) + '.HK'

        logging.info(f"성공! 총 {len(df)}개 기업 정보를 확인합니다.")
        return df

    except Exception as e:
        logging.error(f"{country_name} 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

def filter_by_market_cap_if_needed(df, country_code, config):
    if country_code in ['kr']: # 한국만 yfinance로 시총 필터링
        logging.info(f"총 {len(df)}개 종목의 시가총액 정보 조회 시작 (시간 소요)...")
        market_caps = []
        for i, ticker in enumerate(df['Ticker']):
            if (i + 1) % 50 == 0: logging.info(f"--> 시총 조회 진행: [{i+1}/{len(df)}]")
            try:
                info = yf.Ticker(ticker).info
                if 'marketCap' in info and info['marketCap'] is not None:
                    market_caps.append({'Ticker': ticker, 'MarketCap': info['marketCap']})
            except Exception:
                continue
        
        df_caps = pd.DataFrame(market_caps)
        df = df_caps.sort_values(by='MarketCap', ascending=False).head(config.get('top_n', 1500))
        logging.info(f"시가총액 상위 {len(df)}개 기업으로 필터링 완료.")
    return df

def find_52_week_high_stocks_from_df(stocks_df, country_config):
    if stocks_df.empty: return []
    high_stocks = []
    total_stocks = len(stocks_df)
    currency = country_config['currency_symbol']
    logging.info(f"\n총 {total_stocks}개 종목에 대해 52주 신고가 스크리닝 시작...")
    
    for index, row in stocks_df.iterrows():
        ticker = row['Ticker']
        try:
            logging.info(f"-> [{index+1:04d}/{total_stocks}] {ticker} 분석 중...")
            stock_yf = yf.Ticker(ticker)
            info = stock_yf.info
            hist = stock_yf.history(period="1y", interval="1d")

            if hist.empty: continue
            current_price = info.get('regularMarketPrice', hist['Close'].iloc[-1])
            high_52_week = info.get('fiftyTwoWeekHigh', hist['High'].max())
            if not current_price or not high_52_week: continue

            if current_price >= high_52_week * 0.98:
                market_cap_value = info.get('marketCap', 0)
                stock_data = {
                    'Ticker': ticker, 'Company Name': info.get('longName', row.get('Company', 'N/A')),
                    'Sector': info.get('sector', 'N/A'), 'Industry': info.get('industry', 'N/A'),
                    'Market Cap': f"{currency}{market_cap_value:,}",
                    'P/E (TTM)': f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else 'N/A',
                    'Current Price': f"{currency}{current_price:,.2f}",
                    '52-Week High': f"{currency}{high_52_week:,.2f}",
                }
                high_stocks.append(stock_data)
                logging.info(f"✅ [{index+1:04d}/{total_stocks}] 발견! {ticker}")
        except Exception:
            pass
            
    logging.info("스크리닝 완료!")
    return high_stocks

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COUNTRY_CONFIG:
        print(f"Error: Usage: python {sys.argv[0]} <country_code>")
        print(f"Available codes: {list(COUNTRY_CONFIG.keys())}")
        return

    country_code = sys.argv[1]
    config = COUNTRY_CONFIG[country_code]
    output_filename = f"{country_code}_stocks.json"

    logging.info(f"[{config['name']}] 데이터 업데이트 작업을 시작합니다.")
    
    initial_stocks_df = get_stocks_by_country(country_code, config)

    # ✅ [테스트 로직] IS_TEST_MODE가 True일 때만 목록을 줄입니다.
    if IS_TEST_MODE:
        logging.info(f"--- ⚠️ 테스트 모드: {len(initial_stocks_df)}개 중 {TEST_SAMPLE_SIZE}개만 사용합니다. ---")
        initial_stocks_df = initial_stocks_df.head(TEST_SAMPLE_SIZE)

    filtered_stocks_df = filter_by_market_cap_if_needed(initial_stocks_df, country_code, config)
    found_stocks = find_52_week_high_stocks_from_df(filtered_stocks_df, config)
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(found_stocks, f, ensure_ascii=False, indent=4)
        
    logging.info(f"총 {len(found_stocks)}개의 종목 정보를 {output_filename} 파일에 저장했습니다.")

if __name__ == '__main__':
    main()
