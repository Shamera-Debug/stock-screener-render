import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import logging
import json
import os
import sys
import investpy # ✅ [핵심] investpy 라이브러리 추가

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 최종 국가별 설정
COUNTRY_CONFIG = {
    'us': {
        'name': '미국 (USA)',
        'investpy_country': 'united states',
        'market_cap_filter': '+Large (over $10bln)',
        'currency_symbol': '$'
    },
    'jp': {
        'name': '일본 (Japan)',
        'investpy_country': 'japan',
        'currency_symbol': '¥',
        'top_n': 1500
    },
    'hk': {
        'name': '홍콩 (Hong Kong)',
        'investpy_country': 'hong kong',
        'currency_symbol': 'HK$',
        'top_n': 1500
    },
    'kr': {
        'name': '한국 (Korea)',
        'investpy_country': 'south korea',
        'currency_symbol': '₩',
        'top_n': 1500
    }
}

def get_filtered_stocks(country_code, config):
    country_name = config['name']
    logging.info(f"'{country_name}'의 종목 목록을 가져오는 중...")
    
    try:
        if country_code == 'us':
            # 미국: Finviz의 강력한 필터링 기능 유지
            logging.info(f"finvizfinance를 통해 '{config['market_cap_filter']}' 기준 스크리닝 중...")
            foverview = Overview()
            filters_dict = {'Exchange': ['NASDAQ', 'NYSE'], 'Market Cap.': config['market_cap_filter']}
            foverview.set_filter(filters_dict=filters_dict)
            df = foverview.screener_view(order='Market Cap.', ascend=False)
        else:
            # ✅ [핵심] 그 외 모든 국가는 investpy로 시총 상위 1500개 필터링
            country = config['investpy_country']
            top_n = config.get('top_n', 1500)
            logging.info(f"investpy를 통해 '{country}'의 시가총액 상위 {top_n}개 종목 가져오는 중...")
            
            # investpy로 국가의 모든 주식 정보를 가져옴 (시가총액 포함)
            all_stocks_df = investpy.get_stocks(country=country)

            # --- ✅ [디버깅 코드 추가] ---
            # investpy가 반환한 실제 컬럼 목록을 확인합니다.
            print("===== investpy가 반환한 실제 컬럼 목록 =====")
            print(all_stocks_df.columns.tolist())
            print("==========================================")
            # ------------------------------------
            
            # 시가총액(market_cap)이 높은 순으로 정렬 후 상위 N개 선택
            # market_cap 단위는 백만(million)이므로 큰 숫자가 위로 오도록 정렬
            df = all_stocks_df.sort_values(by='market_cap', ascending=False).head(top_n)
            # yfinance에서 사용할 Ticker를 symbol 컬럼에서 가져옴
            df.rename(columns={'symbol': 'Ticker'}, inplace=True)

        logging.info(f"성공! 총 {len(df)}개 기업 정보를 1차 필터링했습니다.")
        return df

    except Exception as e:
        logging.error(f"{country_name} 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

def find_52_week_high_stocks_from_df(stocks_df, country_config):
    if stocks_df.empty: return []
    high_stocks = []
    total_stocks = len(stocks_df)
    currency = country_config['currency_symbol']
    logging.info(f"\n총 {total_stocks}개 종목에 대해 52주 신고가 스크리닝 시작...")
    
    for index, row in stocks_df.iterrows():
        ticker = row['Ticker']
        
        # investpy가 제공하는 yfinance용 Ticker 사용 (국가별 접미사 자동 처리)
        yfinance_ticker = ticker
        if country_config['investpy_country'] == 'japan':
            yfinance_ticker += '.T'
        elif country_config['investpy_country'] == 'hong kong':
            yfinance_ticker += '.HK'
        elif country_config['investpy_country'] == 'south korea':
            yfinance_ticker += '.KS' # 또는 .KQ 지만 KS가 대부분의 대형주를 커버
            
        try:
            stock_yf = yf.Ticker(yfinance_ticker)
            info = stock_yf.info
            hist = stock_yf.history(period="1y", interval="1d")

            if hist.empty: continue
            current_price = info.get('regularMarketPrice', hist['Close'].iloc[-1])
            high_52_week = info.get('fiftyTwoWeekHigh', hist['High'].max())
            if not current_price or not high_52_week: continue

            if current_price >= high_52_week * 0.98:
                market_cap_value = info.get('marketCap', 0)
                
                stock_data = {
                    'Ticker': ticker,
                    'Company Name': info.get('longName', row.get('name', 'N/A')),
                    'Sector': info.get('sector', 'N/A'),
                    'Industry': info.get('industry', 'N/A'),
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
    
    filtered_stocks_df = get_filtered_stocks(country_code, config)
    found_stocks = find_52_week_high_stocks_from_df(filtered_stocks_df, config)
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(found_stocks, f, ensure_ascii=False, indent=4)
        
    logging.info(f"총 {len(found_stocks)}개의 종목 정보를 {output_filename} 파일에 저장했습니다.")

if __name__ == '__main__':
    main()

