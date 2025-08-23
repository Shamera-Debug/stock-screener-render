import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import logging
import json
import os
import sys
import investpy # pykrx 대신 investpy 사용
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 테스트 설정 ---
IS_TEST_MODE = False
TEST_SAMPLE_SIZE = 30
# --------------------

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 최종 국가별 설정
COUNTRY_CONFIG = {
    'us': { 'name': '미국 (USA)', 'market_cap_filter': '+Large (over $10bln)', 'currency_symbol': '$'},
    'jp': { 'name': '일본 (Japan)', 'investpy_country': 'japan', 'yfinance_suffix': '.T', 'currency_symbol': '¥', 'top_n': 2000 },
    'hk': { 'name': '홍콩 (Hong Kong)', 'investpy_country': 'hong kong', 'yfinance_suffix': '.HK', 'currency_symbol': 'HK$', 'top_n': 2000 },
    'kr': { 'name': '한국 (Korea)', 'investpy_country': 'south korea', 'yfinance_suffix': '.KS', 'currency_symbol': '₩', 'top_n': 2000 }
}

def get_filtered_stocks(country_code, config):
    country_name = config['name']
    logging.info(f"'{country_name}'의 종목 목록을 가져오는 중...")
    
    try:
        if country_code == 'us':
            # 미국: Finviz 사용
            logging.info(f"finvizfinance를 통해 '{config['market_cap_filter']}' 기준 스크리닝 중...")
            foverview = Overview()
            filters_dict = {'Exchange': ['NASDAQ', 'NYSE'], 'Market Cap.': config['market_cap_filter']}
            foverview.set_filter(filters_dict=filters_dict)
            df = foverview.screener_view(order='Market Cap.', ascend=False)
        else:
            # ✅ [수정] 한국, 일본, 홍콩 모두 investpy 사용
            country = config['investpy_country']
            top_n = config.get('top_n', 1500)
            logging.info(f"investpy를 통해 '{country}'의 시가총액 상위 {top_n}개 종목 가져오는 중...")
            
            all_stocks_df = investpy.get_stocks(country=country)
            
            # investpy가 'Market Cap' 컬럼을 제공하는 경우에만 필터링
            if 'Market Cap' in all_stocks_df.columns:
                df = all_stocks_df.sort_values(by='Market Cap', ascending=False).head(top_n)
            else: # 제공하지 않는 경우(예: 구버전)에는 전체 목록 사용
                df = all_stocks_df
            
            df = df.rename(columns={'symbol': 'Ticker'})
            df['Ticker'] = df['Ticker'] + config['yfinance_suffix']

    except Exception as e:
        logging.error(f"{country_name} 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

    logging.info(f"성공! 총 {len(df)}개 기업 정보를 1차 필터링했습니다.")
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

            company_name = info.get('longName')
            sector = info.get('sector')
            industry = info.get('industry')
            
            if not company_name and not sector and not industry:
                logging.info(f"--> {ticker}: 필수 정보(이름, 섹터, 산업) 모두 누락되어 건너뜁니다.")
                continue

            hist = stock_yf.history(period="1y", interval="1d")
            if hist.empty: continue
            
            current_price = info.get('regularMarketPrice', hist['Close'].iloc[-1])
            high_52_week = info.get('fiftyTwoWeekHigh', hist['High'].max())
            if not current_price or not high_52_week: continue

            if current_price >= high_52_week * 0.98:
                market_cap_value = info.get('marketCap', 0)
                stock_data = {
                    'Ticker': ticker,
                    'Company Name': company_name or 'N/A',
                    'Sector': sector or 'N/A',
                    'Industry': industry or 'N/A',
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
    output_filename = os.path.join(BASE_DIR, f"{country_code}_stocks.json")
    backup_filename = os.path.join(BASE_DIR, f"{country_code}_stocks_old.json")

    if os.path.exists(output_filename):
        logging.info(f"기존 데이터 파일 '{output_filename}'을 '{backup_filename}'으로 백업합니다.")
        shutil.copyfile(output_filename, backup_filename)

    logging.info(f"[{config['name']}] 데이터 업데이트 작업을 시작합니다.")
    
    initial_stocks_df = get_filtered_stocks(country_code, config)

    if IS_TEST_MODE:
        logging.info(f"--- ⚠️ 테스트 모드: {len(initial_stocks_df)}개 중 {TEST_SAMPLE_SIZE}개만 사용합니다. ---")
        initial_stocks_df = initial_stocks_df.head(TEST_SAMPLE_SIZE)
    
    found_stocks = find_52_week_high_stocks_from_df(initial_stocks_df, config)
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(found_stocks, f, ensure_ascii=False, indent=4)
        
    logging.info(f"총 {len(found_stocks)}개의 종목 정보를 {output_filename} 파일에 저장했습니다.")

if __name__ == '__main__':
    main()

