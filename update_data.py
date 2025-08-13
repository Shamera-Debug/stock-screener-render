import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import logging
import json
import os
import sys
import requests # ✅ [추가] API 요청을 위한 requests 라이브러리
from pykrx import stock
import openpyxl
import requests # requests 라이브러리 추가
from bs4 import BeautifulSoup # BeautifulSoup 라이브러리 추가



# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# 최종 국가별 설정
COUNTRY_CONFIG = {
    'us': {
        'name': '미국 (USA)',
        'market_cap_filter': '+Large (over $10bln)',
        'currency_symbol': '$'
    },
    'jp': {
        'name': '일본 (Japan)',
        'currency_symbol': '¥'
    },
    'hk': {
        'name': '홍콩 (Hong Kong)',
        'currency_symbol': 'HK$'
    },
    'kr': {
        'name': '한국 (Korea)',
        'currency_symbol': '₩'
    }
}


# ✅ [API 키] 발급받은 EODHD API 키를 여기에 입력하세요.
EODHD_API_KEY = "689b3c81d03518.86648196" 

def get_stocks_by_country(country_code, config):
    country_name = config['name']
    logging.info(f"'{country_name}'의 전체 종목 목록을 가져오는 중...")
    df = pd.DataFrame()
    try:
        if country_code == 'us':
            # 미국: Finviz 사용 (기존과 동일)
            market_cap_filter = config['market_cap_filter']
            all_dfs = []
            for exchange in ['NASDAQ', 'NYSE']:
                logging.info(f"거래소 '{exchange}' 스크리닝 중...")
                foverview = Overview()
                filters_dict = {'Exchange': exchange, 'Market Cap.': market_cap_filter}
                foverview.set_filter(filters_dict=filters_dict)
                exchange_df = foverview.screener_view(order='Market Cap.', ascend=False)
                all_dfs.append(exchange_df)
            df = pd.concat(all_dfs, ignore_index=True)
            # 미국은 여기서 필터링이 끝났으므로 바로 반환
            logging.info(f"성공! 총 {len(df)}개 기업 정보를 확인합니다.")
            return df

        elif country_code == 'kr':
            # 한국: pykrx 사용 (기존과 동일)
            logging.info("pykrx를 통해 KOSPI, KOSDAQ 종목 목록 가져오는 중...")
            kospi = stock.get_market_ticker_list(market="KOSPI")
            kosdaq = stock.get_market_ticker_list(market="KOSDAQ")
            df['Ticker'] = [f"{ticker}.KS" for ticker in kospi] + [f"{ticker}.KQ" for ticker in kosdaq]
    
        elif country_code == 'jp':
            logging.info("일본거래소(JPX) 웹사이트에서 최신 엑셀 파일 링크 찾는 중...")
    
            landing_page_url = "https://www.jpx.co.jp/english/markets/statistics-equities/misc/01.html"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(landing_page_url, headers=headers)
            soup = BeautifulSoup(response.content, 'lxml')
    
            excel_link = soup.find('a', href=lambda href: href and (href.endswith('.xls') or href.endswith('.xlsx')))
    
            if not excel_link:
                raise ValueError("JPX 사이트에서 엑셀 파일 링크를 찾지 못했습니다.")
    
            file_url = "https://www.jpx.co.jp" + excel_link['href']
            logging.info(f"엑셀 파일 다운로드 링크 찾음: {file_url}")
    
            # ✅ [최종 수정 1] 헤더 위치를 정확히 지정 (header=0)
            df_jpx = pd.read_excel(file_url, header=0)
    
            # ✅ [최종 수정 2] 컬럼 이름의 공백 제거 (안정성 강화)
            df_jpx.columns = df_jpx.columns.str.strip()
    
            # ✅ [최종 수정 3] 펀드(ETF/ETN) 등을 제외하고 순수 주식만 필터링
            df_filtered = df_jpx[~df_jpx['Section/Products'].str.contains('ETFs/ ETNs|REITs/ Pro Market|JDRs', na=False)]
    
            df = pd.DataFrame()
            # ✅ [최종 수정 4] 올바른 컬럼 이름('Local Code') 사용
            df['Ticker'] = df_filtered['Local Code'].astype(str) + '.T'

        elif country_code == 'hk':
            # 홍콩: 위키피디아 스크래핑 (기존과 동일)
            logging.info("Wikipedia에서 홍콩 증권거래소 종목 목록 가져오는 중...")
            url = "https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_Hong_Kong_Stock_Exchange"
            tables = pd.read_html(url)
            df_hk = tables[0] # 홍콩은 첫 번째 테이블
            df_hk.rename(columns={'Ticker': 'Stock Code'}, inplace=True, errors='ignore')
            df['Ticker'] = df_hk['Stock Code'].astype(str).str.zfill(4) + '.HK'

        # 미국 외 국가: 시가총액으로 상위 N개 필터링
        logging.info(f"총 {len(df)}개 종목의 시가총액 정보 조회 시작 (시간 소요)...")
        market_caps = []
        for ticker in df['Ticker']:
            try:
                logging.info(f"--> 시총 조회: [{index+1:04d}/{total_stocks}] {ticker}")
                info = yf.Ticker(ticker).info
                market_caps.append({'Ticker': ticker, 'MarketCap': info.get('marketCap', 0)})
            except Exception:
                continue # 개별 종목 조회 실패 시 건너뛰기

        df_caps = pd.DataFrame(market_caps)
        df_caps = df_caps.sort_values(by='MarketCap', ascending=False).head(config.get('top_n', 1000))

        logging.info(f"성공! 시가총액 상위 {len(df_caps)}개 기업 정보를 확인합니다.")
        return df_caps

    except Exception as e:
        logging.error(f"{country_name} 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

def format_market_cap(value, currency):
    if not isinstance(value, (int, float)) or value <= 0:
        return "N/A"
    if value >= 1_000_000_000_000:
        return f"{currency}{value / 1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"{currency}{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{currency}{value / 1_000_000:.2f}M"
    return f"{currency}{value:,}"

def find_52_week_high_stocks_from_df(stocks_df, country_config):
    if stocks_df.empty:
        return []
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
                stock_data = {
                    'Ticker': ticker,
                    'Company Name': info.get('longName', 'N/A'),
                    'Sector': info.get('sector', 'N/A'),
                    'Industry': info.get('industry', 'N/A'),
                    'Market Cap': format_market_cap(info.get('marketCap', 0), currency),
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
    all_stocks_df = get_stocks_by_country(country_code, config)
    found_stocks = find_52_week_high_stocks_from_df(all_stocks_df, config)
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(found_stocks, f, ensure_ascii=False, indent=4)
        
    logging.info(f"총 {len(found_stocks)}개의 종목 정보를 {output_filename} 파일에 저장했습니다.")

if __name__ == '__main__':
    main()















