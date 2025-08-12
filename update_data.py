import yfinance as yf
import pandas as pd
from finvizfinance.screener.overview import Overview
import logging
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 공유 디스크 경로로 수정
DATA_FILE = '/var/data/stocks.json'

# --- ✅ [수정 1] PythonAnywhere 프록시 설정 ---
# 이 딕셔너리를 추가합니다.
proxies = {
   "http": "http://proxy.server:3128",
   "https": "http://proxy.server:3128",
}
# -------------------------------------------

def format_market_cap(cap_string):
    """시가총액 문자열을 B(10억), T(조) 단위로 변환하는 함수"""
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
            return f"${float(cap_string):,.0f}" # B, T, M이 없는 경우 원래 숫자 표시
    except (ValueError, TypeError):
        return cap_string

def get_nasdaq_top500_stocks():
    logging.info("finvizfinance 스크리너를 통해 나스닥 시총 상위 500개 주식을 불러오는 중...")
    try:
        foverview = Overview()
        filters_dict = {
            'Exchange': 'NASDAQ',
            'Market Cap.': '+Mid (over $2bln)',
            'Industry': 'Stocks only (ex-Funds)',
        }
        foverview.set_filter(filters_dict=filters_dict)
        
        # --- ✅ [수정 2] finvizfinance에 프록시 적용 ---
        df = foverview.screener_view(order='Market Cap.', ascend=False, proxy=proxies)
        # ---------------------------------------------
        
        df_top500 = df.head(500).copy()
        logging.info(f"성공! 나스닥 시가총액 상위 {len(df_top500)}개 기업 정보를 확인합니다.")
        return df_top500
    except Exception as e:
        logging.error(f"나스닥 상위 기업 목록을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame()

def find_52_week_high_stocks_from_df(stocks_df):
    if stocks_df.empty:
        return []
    high_stocks = []
    logging.info("\n52주 신고가 종목 스크리닝 시작...")
    total_stocks = len(stocks_df)
    for index, row in stocks_df.iterrows():
        ticker = row['Ticker']
        try:
            # --- ✅ [수정 3] yfinance에 프록시 적용 ---
            stock_yf = yf.Ticker(ticker, proxy=proxies)
            # ----------------------------------------
            
            hist = stock_yf.history(period="1y")
            if hist.empty:
                continue
            
            current_price = hist['Close'][-1]
            high_52_week = hist['High'].max()
            
            if current_price >= high_52_week * 0.98:
                stock_data = {
                    'Ticker': ticker,
                    'Company Name': row.get('Company', 'N/A'),
                    'Sector': row.get('Sector', 'N/A'),
                    'Industry': row.get('Industry', 'N/A'),
                    'Market Cap': format_market_cap(row.get('Market Cap')),
                    'P/E (TTM)': row.get('P/E', 'N/A'),
                    'Current Price': f"${current_price:,.2f}",
                    '52-Week High': f"${high_52_week:,.2f}",
                }
                high_stocks.append(stock_data)
                logging.info(f"✅ [{index+1:03d}/{total_stocks}] 발견! {ticker}")
        except Exception as e:
            logging.warning(f"종목 {ticker} 정보 조회 중 오류 발생: {e}")
            pass
    logging.info("스크리닝 완료!")
    return high_stocks

def main():
    """데이터를 가져와 JSON 파일로 저장하는 메인 함수"""
    logging.info("데이터 업데이트 작업을 시작합니다.")
    top_500_df = get_nasdaq_top500_stocks()
    found_stocks = find_52_week_high_stocks_from_df(top_500_df)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(found_stocks, f, ensure_ascii=False, indent=4)
        
    logging.info(f"총 {len(found_stocks)}개의 종목 정보를 {DATA_FILE} 파일에 저장했습니다.")
    logging.info("데이터 업데이트 작업을 완료했습니다.")

if __name__ == '__main__':
    main()