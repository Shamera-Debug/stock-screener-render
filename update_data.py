import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import logging
import json
import os
import sys # 명령줄 인자를 받기 위해 추가

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ✅ [수정] 해외 국가의 market_cap 필터를 빈 문자열('')로 변경
COUNTRY_CONFIG = {
    'us': {
        'name': '미국 (USA)',
        'filter_type': 'exchange',
        'filter_value': ['NASDAQ', 'NYSE'],
        'market_cap': '+Large (over $10bln)', # 미국은 기준 유지
        'currency_symbol': '$'
    },
    'jp': {
        'name': '일본 (Japan)',
        'filter_type': 'country',
        'filter_value': 'Japan',
        'market_cap': '', # 시가총액 필터 제거
        'currency_symbol': '¥'
    },
    'hk': {
        'name': '홍콩 (Hong Kong)',
        'filter_type': 'country',
        'filter_value': 'Hong Kong',
        'market_cap': '', # 시가총액 필터 제거
        'currency_symbol': 'HK$'
    },
    'kr': {
        'name': '한국 (Korea)',
        'filter_type': 'country',
        'filter_value': 'South Korea',
        'market_cap': '', # 시가총액 필터 제거
        'currency_symbol': '₩'
    }
}

# ✅ [수정] market_cap 필터가 있을 때만 적용하도록 로직 변경
def get_stocks_by_country(country_config):
    country_name = country_config['name']
    filter_type = country_config['filter_type']
    filter_value = country_config['filter_value']
    market_cap_filter = country_config['market_cap']
    
    logging.info(f"finvizfinance 스크리너를 통해 {country_name} 기업 정보를 불러오는 중...")

    if not isinstance(filter_value, list):
        filter_value = [filter_value]

    all_dfs = []
    try:
        for value in filter_value:
            logging.info(f"필터링 기준 '{value}' 스크리닝 중...")
            foverview = Overview()
            
            # 기본 필터 설정
            if filter_type == 'exchange':
                filters_dict = {'Exchange': value}
            else: # 'country'
                filters_dict = {'Country': value}
            
            # market_cap 필터 값이 있을 경우에만 추가
            if market_cap_filter:
                filters_dict['Market Cap.'] = market_cap_filter
            
            foverview.set_filter(filters_dict=filters_dict)
            df = foverview.screener_view(order='Market Cap.', ascend=False)
            all_dfs.append(df)
        
        combined_df = pd.concat(all_dfs, ignore_index=True)
        logging.info(f"성공! 총 {len(combined_df)}개 기업 정보를 확인합니다.")
        return combined_df
        
    except Exception as e:
        logging.error(f"{country_name} 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

# 상세 정보를 스크리닝하는 함수 (통화 기호 추가)
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
            stock_yf = yf.Ticker(ticker)
            info = stock_yf.info
            hist = stock_yf.history(period="1y", interval="1d")

            if hist.empty or 'regularMarketPrice' not in info or 'fiftyTwoWeekHigh' not in info:
                continue

            current_price = info['regularMarketPrice']
            high_52_week = info['fiftyTwoWeekHigh']

            if current_price >= high_52_week * 0.98:
                market_cap_value = info.get('marketCap', 0)
                market_cap_str = f"{currency}{market_cap_value:,}"

                stock_data = {
                    'Ticker': ticker,
                    'Company Name': info.get('longName', 'N/A'),
                    'Sector': info.get('sector', 'N/A'),
                    'Industry': info.get('industry', 'N/A'),
                    'Market Cap': market_cap_str,
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

# ✅ [수정] 메인 함수: 명령줄 인자를 받아 처리
def main():
    # python update_data.py us 와 같이 실행하면 'us'를 인자로 받음
    if len(sys.argv) < 2 or sys.argv[1] not in COUNTRY_CONFIG:
        print("Error: Please provide a valid country code.")
        print(f"Available codes: {list(COUNTRY_CONFIG.keys())}")
        return

    country_code = sys.argv[1]
    config = COUNTRY_CONFIG[country_code]
    output_filename = f"{country_code}_stocks.json" # 국가별 파일 이름 생성

    logging.info(f"[{config['name']}] 데이터 업데이트 작업을 시작합니다.")
    
    all_stocks_df = get_stocks_by_country(config)
    found_stocks = find_52_week_high_stocks_from_df(all_stocks_df, config)
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(found_stocks, f, ensure_ascii=False, indent=4)
        
    logging.info(f"총 {len(found_stocks)}개의 종목 정보를 {output_filename} 파일에 저장했습니다.")
    logging.info("데이터 업데이트 작업을 완료했습니다.")

if __name__ == '__main__':
    main()





