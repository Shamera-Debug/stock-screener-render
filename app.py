from flask import Flask, render_template
import json
import logging

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
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            found_stocks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        found_stocks = []

    return render_template('index.html', 
                           stocks=found_stocks, 
                           countries=COUNTRY_CONFIG.items(),
                           active_country_code=country_code,
                           country_name=COUNTRY_CONFIG[country_code]['name'])

if __name__ == '__main__':
    app.run(host='0.0.0.0')
