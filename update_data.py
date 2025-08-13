import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import logging
import json
import os
import sys
from openbb import obb

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 최종 국가별 설정
COUNTRY_CONFIG = {
    'us': { 'name': '미국 (USA)', 'market_cap_filter': '+Large (over $10bln)', 'currency_symbol': '$'},
    'jp': { 'name': '일본 (Japan)', 'openbb_country': 'japan', 'yfinance_suffix': '.T', 'currency_symbol': '¥', 'top_n': 1500 },
    'hk': { 'name': '홍콩 (Hong Kong)', 'openbb_country': 'hong_kong', 'yfinance_suffix': '.HK', 'currency_symbol': 'HK$', 'top_n': 1500 },
    'kr': { 'name': '한국 (Korea)', 'openbb_country': 'south_korea', 'yfinance_suffix': '.KS', 'currency_symbol': '₩', 'top_n': 1500 }
}

def get_filtered_stocks(country_code, config):
    country_name = config['name']
    logging.info(f"'{country_name}'의 종목 목록을 가져오는 중...")
    
    try:
        if country_code == 'us':
            # 미국은 현재 문제가 없으므로 그대로 둡니다.
            logging.info(f"finvizfinance를 통해 '{config['market_cap_filter']}' 기준 스크리닝 중...")
            foverview = Overview()
            filters_dict = {'Exchange': ['NASDAQ', 'NYSE'], 'Market Cap.': config['market_cap_filter']}
            foverview.set_filter(filters_dict=filters_dict)
            df = foverview.screener_view(order='Market Cap.', ascend=False)
        else:
            # 해외 국가 디버깅 시작
            country = config['openbb_country']
            
            # --- 1단계: obb.equity.search 결과 확인 ---
            logging.info(f"OpenBB: '{country}'의 전체 증권 목록 가져오는 중...")
            all_securities_df = obb.equity.search(country=country).to_df()
            
            print("\n\n===== [디버그 1] obb.equity.search 결과 =====")
            print("--- 처음 5줄 ---")
            print(all_securities_df.head())
            print("\n--- 전체 컬럼 목록 ---")
            print(all_securities_df.columns.tolist())
            print("==========================================\n\n")

            symbols_list = all_securities_df['symbol'].tolist()
            
            # 테스트를 위해 50개만 사용
            logging.info(f"--- 테스트 모드: {len(symbols_list)}개 중 50개만 사용합니다. ---")
            symbols_list = symbols_list[:50]

            if not symbols_list:
                raise ValueError(f"OpenBB에서 '{country}'의 Ticker 목록을 찾을 수 없습니다.")

            # --- 2단계: obb.equity.price.quote 결과 확인 (핵심) ---
            logging.info(f"OpenBB: 총 {len(symbols_list)}개 증권의 시세 정보 조회 중...")
            quote_df = obb.equity.price.quote(symbol=symbols_list).to_df()

            print("\n\n===== [디버그 2] obb.equity.price.quote 결과 =====")
            print("--- 처음 5줄 ---")
            print(quote_df.head())
            print("\n--- 전체 컬럼 목록 ---")
            print(quote_df.columns.tolist())
            print("=============================================\n\n")

            # 디버깅을 위해 여기서 함수를 안전하게 종료합니다.
            logging.info("디버깅 출력이 완료되었습니다. 이 결과를 바탕으로 코드를 최종 수정할 수 있습니다.")
            return pd.DataFrame() # 빈 데이터프레임 반환

    except Exception as e:
        logging.error(f"{country_name} 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

    logging.info(f"성공! 총 {len(df)}개 기업 정보를 1차 필터링했습니다.")
    return df

# --- find_52_week_high_stocks_from_df와 main 함수는 이전 버전과 동일합니다 ---
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
                market_cap_value = info.get('marketCap', row.get('marketCap', 0))
                
                stock_data = {
                    'Ticker': ticker,
                    'Company Name': info.get('longName', row.get('name', 'N/A')),
                    'Sector': info.get('sector', 'N/A'),
                    'Industry': info.get('industry', 'N/A'),
                    'Market Cap': f"{currency}{market_cap_value:,}",
                    'P/E (TTM)': f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else 'N/A',
                    'Current Price': f"{currency}{current_price:,.2f}",
                    '52-Week High': f"{currency}{high_52_week:.2f}",
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




