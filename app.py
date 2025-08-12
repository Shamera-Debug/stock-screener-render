from flask import Flask, render_template
import json
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# 국가 설정 정보를 app.py에서도 사용
COUNTRY_CONFIG = {
    'us': {'name': '미국 (USA)'},
    'jp': {'name': '일본 (Japan)'},
    'hk': {'name': '홍콩 (Hong Kong)'},
    'kr': {'name': '한국 (Korea)'}
}

# ✅ [수정] 기본 경로와 국가별 경로를 모두 처리하는 동적 라우트
@app.route('/')
@app.route('/<string:country_code>')
def index(country_code='us'): # 기본값을 'us'로 설정
    if country_code not in COUNTRY_CONFIG:
        country_code = 'us' # 잘못된 코드가 들어오면 미국으로

    data_file = f"{country_code}_stocks.json"
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            found_stocks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        found_stocks = []

    # ✅ [수정] HTML 템플릿에 더 많은 정보를 전달
    return render_template('index.html', 
                           stocks=found_stocks, 
                           countries=COUNTRY_CONFIG.items(),
                           active_country_code=country_code,
                           country_name=COUNTRY_CONFIG[country_code]['name'])

if __name__ == '__main__':
    app.run(host='0.0.0.0')
