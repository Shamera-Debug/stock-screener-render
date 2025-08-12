from flask import Flask, render_template
import json
import logging

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

DATA_FILE = 'stocks.json'

@app.route('/')
def index():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            found_stocks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # 파일이 없거나 비어있으면 빈 리스트를 전달
        found_stocks = []

    return render_template('index.html', stocks=found_stocks)

if __name__ == '__main__':
    # 로컬 테스트용이 아닌, gunicorn으로 실행될 예정
    app.run(host='0.0.0.0')
