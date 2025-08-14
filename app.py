from flask import Flask, render_template, redirect, url_for
import json
import logging
import os
from datetime import datetime, timedelta

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COUNTRY_CONFIG = { 'us': {'name': '미국 (USA)'}, 'jp': {'name': '일본 (Japan)'}, 'hk': {'name': '홍콩 (Hong Kong)'}, 'kr': {'name': '한국 (Korea)'} }

@app.route('/')
def home():
    return redirect(url_for('index', country_code='us'))

@app.route('/<string:country_code>')
def index(country_code):
    if country_code not in COUNTRY_CONFIG:
        return redirect(url_for('index', country_code='us'))

    data_file = os.path.join(BASE_DIR, f"{country_code}_stocks.json")
    backup_file = os.path.join(BASE_DIR, f"{country_code}_stocks_old.json")
    
    last_updated_str = "데이터 없음"
    found_stocks = []
    
    try:
        if os.path.exists(data_file):
            # 이전 데이터(old) Ticker 목록 불러오기
            old_tickers = set()
            if os.path.exists(backup_file):
                with open(backup_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content:
                        old_data = json.loads(content)
                        old_tickers = {stock['Ticker'] for stock in old_data}
            
            # 현재 데이터(new) 불러오기 및 신규 종목 태그 추가
            with open(data_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    new_data = json.loads(content)
                    for stock in new_data:
                        if stock['Ticker'] not in old_tickers:
                            stock['is_new'] = True # 신규 종목에 꼬리표 달기
                    found_stocks = new_data
            
            # 업데이트 시간 계산
            utc_timestamp = os.path.getmtime(data_file)
            kst_time = datetime.fromtimestamp(utc_timestamp) + timedelta(hours=9)
            last_updated_str = kst_time.strftime('%Y-%m-%d %H:%M KST')
                
    except Exception as e:
        logging.error(f"Error processing files: {e}")

    return render_template('index.html', 
                           stocks=found_stocks, countries=COUNTRY_CONFIG.items(),
                           active_country_code=country_code,
                           country_name=COUNTRY_CONFIG[country_code]['name'],
                           last_updated=last_updated_str)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
