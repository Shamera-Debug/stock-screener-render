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

# 국가별 설정 (테스트용)
COUNTRY_CONFIG = {
    'us': { 'name': '미국 (USA)', 'market_cap_filter': '+Large (over $10bln)', 'currency_symbol': '$'},
    'jp': { 'name': '일본 (Japan)', 'exchange_country': 'JP', 'yfinance_suffix': '.T', 'currency_symbol': '¥' },
    'hk': { 'name': '홍콩 (Hong Kong)', 'exchange_country': 'HK', 'yfinance_suffix': '.HK', 'currency_symbol': 'HK$' },
    'kr': { 'name': '한국 (Korea)', 'exchange_country': 'KR', 'yfinance_suffix': '.KS', 'currency_symbol': '₩' }
}

def get_filtered_stocks_debug(country_code, config):
    country_name = config['name']
    logging.info(f"'{country_name}'의 종목 목록을 가져오는 중 (디버그 모드)...")
    
    try:
        if country_code == 'us':
            print("미국(us)은 현재 문제가 없으므로 테스트를 건너뜁니다.")
            return pd.DataFrame()
        else:
            exchange_country = config['exchange_country']
            
            # --- 1단계: obb.equity.search 결과 확인 ---
            logging.info(f"OpenBB: '{exchange_country}' 거래소의 전체 Ticker 목록 가져오는 중...")
            all_securities_df = obb.equity.search(exchange_country=exchange_country).to_df()
            
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
                raise ValueError("Ticker 목록을 찾을 수 없습니다.")

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
            return pd.DataFrame()

    except Exception as e:
        logging.error(f"{country_name} 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COUNTRY_CONFIG:
        print(f"Error: Usage: python {sys.argv[0]} <country_code>")
        print(f"Available codes: {list(COUNTRY_CONFIG.keys())}")
        return

    country_code = sys.argv[1]
    config = COUNTRY_CONFIG[country_code]
    output_filename = f"{country_code}_stocks.json"

    logging.info(f"[{config['name']}] 데이터 업데이트 작업을 시작합니다.")
    
    # 디버깅용 함수를 호출하도록 수정
    get_filtered_stocks_debug(country_code, config)
        
    logging.info(f"총 0개의 종목 정보를 {output_filename} 파일에 저장했습니다. (디버그 모드)")

if __name__ == '__main__':
    main()
