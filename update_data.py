import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import logging
import json
import os
import sys
from pykrx import stock
import investpy
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
    'jp': { 'name': '일본 (Japan)', 'investpy_country': 'japan', 'yfinance_suffix': '.T', 'currency_symbol': '¥', 'top_n': 1500 },
    'hk': { 'name': '홍콩 (Hong Kong)', 'investpy_country': 'hong kong', 'yfinance_suffix': '.HK', 'currency_symbol': 'HK$', 'top_n': 1500 },
    'kr': { 'name': '한국 (Korea)', 'yfinance_suffix': '.KS', 'currency_symbol': '₩', 'top_n': 1500 }
}

def get_stocks_by_country(country_code, config):
    country_name = config['name']
    logging.info(f"'{country_name}'의 전체 종목 목록을 가져오는 중...")
    df = pd.DataFrame()
    try:
        if country_code == 'us':
            market_cap_filter = config['market_cap_filter']
            all_dfs = []
            for exchange in ['NASDAQ', 'NYSE']:
                logging.info(f"finvizfinance를 통해 '{exchange}' 거래소 스크리닝 중...")
                foverview = Overview()
                filters_dict = {'Exchange': exchange, 'Market Cap.': market_cap_filter}
                foverview.set_filter(filters_dict=filters_dict)
                exchange_df = foverview.screener_view(order='Market Cap.', ascend=False)
                all_dfs.append(exchange_df)
            df = pd.concat(all_dfs, ignore_index=True)

        elif country_code == 'kr':
            # ✅ [수정] 한국: pykrx로 Ticker와 '한글 회사명'을 함께 가져옵니다.
            logging.info("pykrx를 통해 KOSPI, KOSDAQ 전 종목 Ticker 및 회사명 가져오는 중...")
            all_tickers_info = []
            for market in ["KOSPI", "KOSDAQ"]:
                tickers = stock.get_market_ticker_list(market=market)
                suffix = ".KS" if market == "KOSPI" else ".KQ"
                for ticker in tickers:
                    # Ticker와 한글 회사명을 함께 저장
                    all_tickers_info.append({
                        'Ticker': f"{ticker}{suffix}",
                        'KoreanName': stock.get_market_ticker_name(ticker)
                    })
            df = pd.DataFrame(all_tickers_info)

        elif country_code in ['jp', 'hk']:
            # 일본, 홍콩: investpy 사용
            country = config['investpy_country']
            logging.info(f"investpy를 통해 '{country}'의 전체 종목 목록 가져오는 중...")
            stocks_df = investpy.get_stocks(country=country)
            df['Ticker'] = stocks_df['symbol'] + config['yfinance_suffix']
        
        logging.info(f"성공! 총 {len(df)}개 기업 정보를 확인합니다.")
        return df

    except Exception as e:
        logging.error(f"{country_name} 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

def filter_by_market_cap(df, country_code, config):
    # 미국은 Finviz에서 이미 필터링되었으므로, 그 외 국가에만 시총 필터링 적용
    if country_code not in ['us']:
        top_n = config.get('top_n', 1500)
        logging.info(f"총 {len(df)}개 종목의 시가총액 정보 조회 시작 (상위 {top_n}개 필터링)...")
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
        if not df_caps.empty:
            # ✅ [수정] 새로운 DF를 만드는 대신, 기존 DF에 시총 정보를 합칩니다.
            # 'Ticker'를 기준으로 두 데이터를 합치므로 'KoreanName' 컬럼이 보존됩니다.
            df = pd.merge(df, df_caps, on='Ticker', how='inner')
            df = df.sort_values(by='MarketCap', ascending=False).head(top_n)
            logging.info(f"시가총액 상위 {len(df)}개 기업으로 필터링 완료.")
        else:
            df = pd.DataFrame()
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

            if current_price >= high_52_week * 0.97:
                market_cap_value = info.get('marketCap', 0)
                stock_data = {
                    'Ticker': ticker,
                    # ✅ [수정] yfinance의 영문 이름 대신, row에 담겨있는 한글 이름을 사용
                    'Company Name': row.get('KoreanName', info.get('longName', 'N/A')),
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
    output_filename = os.path.join(BASE_DIR, f"{country_code}_stocks.json")
    backup_filename = os.path.join(BASE_DIR, f"{country_code}_stocks_old.json")

    if os.path.exists(output_filename):
        logging.info(f"기존 데이터 파일 '{output_filename}'을 '{backup_filename}'으로 백업합니다.")
        shutil.copyfile(output_filename, backup_filename)

    logging.info(f"[{config['name']}] 데이터 업데이트 작업을 시작합니다.")

    # ✅ [수정] 올바른 함수 이름으로 호출합니다.
    initial_stocks_df = get_stocks_by_country(country_code, config)

    if IS_TEST_MODE:
        logging.info(f"--- ⚠️ 테스트 모드: {len(initial_stocks_df)}개 중 {TEST_SAMPLE_SIZE}개만 사용합니다. ---")
        initial_stocks_df = initial_stocks_df.head(TEST_SAMPLE_SIZE)

    filtered_stocks_df = filter_by_market_cap(initial_stocks_df, country_code, config)
    found_stocks = find_52_week_high_stocks_from_df(filtered_stocks_df, config)

    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(found_stocks, f, ensure_ascii=False, indent=4)

    logging.info(f"총 {len(found_stocks)}개의 종목 정보를 {output_filename} 파일에 저장했습니다.")

if __name__ == '__main__':
    main()





