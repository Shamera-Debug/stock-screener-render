from flask import Flask, render_template
import json
import logging
import os
from datetime import datetime, timedelta

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

COUNTRY_CONFIG = {
    'us': {'name': '미국 (USA)'},
    'jp': {'name': '일본 (Japan)'},
    'hk': {'name': '홍콩 (Hong Kong)'},
    'kr': {'name': '한국 (Korea)'}
}

@app.route('/')
@app.route('/<string:country_code>')
def index(country_code='us'):
    if country_code not in COUNTRY_CONFIG:
        country_code = 'us'

    data_file = f"{country_code}_stocks.json"
    last_updated_str = "N/A"
    
    try:
        # ✅ [수정] 파일의 최종 수정 시간을 가져옵니다.
        # os.path.getmtime은 UTC 기준 타임스탬프를 반환합니다.
        utc_timestamp = os.path.getmtime(data_file)
        # UTC 시간을 KST(UTC+9)로 변환합니다.
        kst_time = datetime.fromtimestamp(utc_timestamp) + timedelta(hours=9)
        last_updated_str = kst_time.strftime('%Y-%m-%d %H:%M KST')

        with open(data_file, 'r', encoding='utf-8') as f:
            found_stocks = json.load(f)

    except (FileNotFoundError, json.JSONDecodeError):
        found_stocks = []

    return render_template('index.html', 
                           stocks=found_stocks, 
                           countries=COUNTRY_CONFIG.items(),
                           active_country_code=country_code,
                           country_name=COUNTRY_CONFIG[country_code]['name'],
                           last_updated=last_updated_str) # ✅ [수정] 업데이트 시간을 전달

if __name__ == '__main__':
    app.run(host='0.0.0.0')
