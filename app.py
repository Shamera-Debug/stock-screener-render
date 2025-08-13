from flask import Flask, render_template, redirect, url_for # ✅ redirect, url_for 추가
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
def home():
    # ✅ [수정] 기본 경로는 /us 로 자동 이동(리다이렉트)시킵니다.
    return redirect(url_for('index', country_code='us'))

@app.route('/<string:country_code>')
def index(country_code):
    # ✅ [수정] 존재하지 않는 국가 코드로 접속 시, /us로 자동 이동시킵니다.
    if country_code not in COUNTRY_CONFIG:
        return redirect(url_for('index', country_code='us'))

    data_file = f"{country_code}_stocks.json"
    last_updated_str = "데이터 없음" # 기본값 변경
    found_stocks = []
    
    try:
        # 파일이 존재할 경우에만 시간 읽기 및 데이터 로드 시도
        if os.path.exists(data_file):
            utc_timestamp = os.path.getmtime(data_file)
            kst_time = datetime.fromtimestamp(utc_timestamp) + timedelta(hours=9)
            last_updated_str = kst_time.strftime('%Y-%m-%d %H:%M KST')

            with open(data_file, 'r', encoding='utf-8') as f:
                # 파일이 비어있는 경우를 대비
                content = f.read()
                if content:
                    found_stocks = json.loads(content)
                
    except Exception as e:
        logging.error(f"Error processing file {data_file}: {e}")
        # 오류 발생 시에도 페이지는 렌더링되도록 빈 데이터를 유지

    return render_template('index.html', 
                           stocks=found_stocks, 
                           countries=COUNTRY_CONFIG.items(),
                           active_country_code=country_code,
                           country_name=COUNTRY_CONFIG[country_code]['name'],
                           last_updated=last_updated_str)

if __name__ == '__main__':
    app.run(host='0.0.0.0')
