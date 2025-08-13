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
            # 미국: Finviz의 강력한 필터링 기능 유지
            logging.info(f"finvizfinance를 통해 '{config['market_cap_filter']}' 기준 스크리닝 중...")
            foverview = Overview()
            filters_dict = {'Exchange': ['NASDAQ', 'NYSE'], 'Market Cap.': config['market_cap_filter']}
            foverview.set_filter(filters_dict=filters_dict)
            df = foverview.screener_view(order='Market Cap.', ascend=False)
        else:
            # ✅ [최적화] OpenBB의 'search'와 'quote' 기능을 조합한 3단계 필터링
            country = config['openbb_country']
            top_n = config.get('top_n', 1500)
            
            # 1단계: 해당 국가의 전체 Ticker 목록 가져오기
            logging.info(f"OpenBB: '{country}'의 전체 Ticker 목록 가져오는 중...")
            all_symbols_df = obb.equity.search(country=country).to_df()
            # '주식(Stock)' 타입만 필터링하여 정확도 향상
            stocks_only_df = all_symbols_df[all_symbols_df['type'] == 'Stock'].copy()
            symbols_list = stocks_only_df['symbol'].tolist()
            
            if not symbols_list:
                raise ValueError(f"OpenBB에서 '{country}'의 Ticker 목록을 찾을 수 없습니다.")

            # 2단계: 필터링된 주식 목록의 시세 정보(시가총액 포함)를 일괄 조회
            logging.info(f"OpenBB: 총 {len(symbols_list)}개 주식의 시세 정보 조회 중 (시간 단축)...")
            quote_df = obb.equity.price.quote(symbol=symbols_list).to_df()
            
            # 3단계: 시가총액(marketCap) 기준으로 상위 N개 필터링
            df_filtered = quote_df.sort_values(by='marketCap', ascending=False).head(top_n)
            
            # yfinance에서 사용할 Ticker 컬럼 생성
            df = df_filtered.copy()
            df['Ticker'] = df.index + config['yfinance_suffix']

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
