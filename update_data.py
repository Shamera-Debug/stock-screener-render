import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import logging
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 데이터를 저장할 파일 이름
DATA_FILE = 'stocks.json'

def format_market_cap(cap_string):
    if not isinstance(cap_string, str):
        return 'N/A'
    cap_string = cap_string.upper()
    try:
        if 'T' in cap_string:
            num = float(cap_string.replace('T', ''))
            return f"{num:,.2f}T"
        elif 'B' in cap_string:
            num = float(cap_string.replace('B', ''))
            return f"{num:,.2f}B"
        elif 'M' in cap_string:
            num = float(cap_string.replace('M', ''))
            return f"{num:,.2f}M"
        else:
            return f"${float(cap_string):,.0f}"
    except (ValueError, TypeError):
        return cap_string

def get_nasdaq_market_cap_stocks():
    logging.info("finvizfinance 스크리너를 통해 나스닥 기업 정보를 불러오는 중...")
    try:
        foverview = Overview()
        # 시가총액 20억 달러(2B) 이상 기업을 대상으로 합니다.
        filters_dict = {
            'Exchange': 'NASDAQ',
            'Market Cap.': '+Mid (over $2bln)',
            'Industry': 'Stocks only (ex-Funds)',
        }
        foverview.set_filter(filters_dict=filters_dict)
        df = foverview.screener_view(order='Market Cap.', ascend=False)
        logging.info(f"성공! 총 {len(df)}개 기업 정보를 확인합니다.")
        return df
    except Exception as e:
        logging.error(f"나스닥 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

def find_52_week_high_stocks_from_df(stocks_df):
    if stocks_df.empty:
        return []
    high_stocks = []
    total_stocks = len(stocks_df)
    logging.info(f"\n총 {total_stocks}개 종목에 대해 52주 신고가 스크리닝 시작...")
    
    for index, row in stocks_df.iterrows():
        ticker = row['Ticker']
        try:
            stock_yf = yf.Ticker(ticker)
            hist = stock_yf.history(period="1y", interval="1d")
            if hist.empty:
                continue
            
            # ✅ [수정 1] yfinance의 info 객체를 가져옵니다.
            info = stock_yf.info
            
            current_price = hist['Close'].iloc[-1]
            high_52_week = hist['High'].max()
            
            if current_price >= high_52_week * 0.98:
                # ✅ [수정 2] 시가총액을 info 객체에서 직접 가져옵니다.
                market_cap_value = info.get('marketCap', 0)
                # 시가총액을 읽기 쉽게 B, T 단위로 변환
                if market_cap_value > 1_000_000_000_000:
                    market_cap_str = f"{market_cap_value / 1_000_000_000_000:.2f}T"
                elif market_cap_value > 1_000_000_000:
                    market_cap_str = f"{market_cap_value / 1_000_000_000:.2f}B"
                elif market_cap_value > 1_000_000:
                    market_cap_str = f"{market_cap_value / 1_000_000:.2f}M"
                else:
                    market_cap_str = f"${market_cap_value:,}"

                stock_data = {
                    'Ticker': ticker,
                    'Company Name': info.get('longName', row.get('Company', 'N/A')), # info 이름이 더 정확
                    'Sector': info.get('sector', row.get('Sector', 'N/A')),
                    'Industry': info.get('industry', row.get('Industry', 'N/A')),
                    'Market Cap': market_cap_str, # ✅ 수정된 시가총액 적용
                    'P/E (TTM)': f"{info.get('trailingPE', 0):.2f}",
                    'Current Price': f"${current_price:,.2f}",
                    '52-Week High': f"${high_52_week:,.2f}",
                }
                high_stocks.append(stock_data)
                logging.info(f"✅ [{index+1:04d}/{total_stocks}] 발견! {ticker}")

        except Exception as e:
            logging.warning(f"종목 {ticker} 정보 조회 중 오류: {e}")
            pass
            
    logging.info("스크리닝 완료!")
    return high_stocks

def main():
    logging.info("데이터 업데이트 작업을 시작합니다.")
    all_stocks_df = get_nasdaq_market_cap_stocks()
    found_stocks = find_52_week_high_stocks_from_df(all_stocks_df)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(found_stocks, f, ensure_ascii=False, indent=4)
        
    logging.info(f"총 {len(found_stocks)}개의 종목 정보를 {DATA_FILE} 파일에 저장했습니다.")
    logging.info("데이터 업데이트 작업을 완료했습니다.")

if __name__ == '__main__':
    main()
