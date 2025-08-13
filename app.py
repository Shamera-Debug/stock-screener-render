from flask import Flask, render_template, redirect, url_for
import json
import logging
import os
from datetime import datetime, timedelta

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# ✅ [수정] 스크립트가 있는 폴더의 절대 경로를 기준으로 삼습니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

COUNTRY_CONFIG = {
    'us': {'name': '미국 (USA)'},
    'jp': {'name': '일본 (Japan)'},
    'hk': {'name': '홍콩 (Hong Kong)'},
    'kr': {'name': '한국 (Korea)'}
}

@app.route('/')
def home():
    return redirect(url_for('index', country_code='us'))

@app.route('/<string:country_code>')
def index(country_code):
    if country_code not in COUNTRY_CONFIG:
        return redirect(url_for('index', country_code='us'))

    # ✅ [수정] 절대 경로를 사용하여 데이터 파일의 위치를 명확히 지정합니다.
    data_file = os.path.join(BASE_DIR, f"{country_code}_stocks.json")
    
    logging.info(f"Request for country: '{country_code}', trying to open: '{data_file}'")

    last_updated_str = "데이터 없음"
    found_stocks = []
    
    try:
        if os.path.exists(data_file):
            utc_timestamp = os.path.getmtime(data_file)
            kst_time = datetime.fromtimestamp(utc_timestamp) + timedelta(hours=9)
            last_updated_str = kst_time.strftime('%Y-%m-%d %H:%M KST')

            with open(data_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    found_stocks = json.loads(content)
                
    except Exception as e:
        logging.error(f"Error processing file {data_file}: {e}")

    return render_template('index.html', 
                           stocks=found_stocks, 
                           countries=COUNTRY_CONFIG.items(),
                           active_country_code=country_code,
                           country_name=COUNTRY_CONFIG[country_code]['name'],
                           last_updated=last_updated_str)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
