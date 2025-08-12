from flask import Flask, render_template
import json
import logging

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# 공유 디스크 경로로 수정
DATA_FILE = '/var/data/stocks.json'

@app.route('/')
def index():
    """메인 페이지를 위한 함수"""
    try:
        # 데이터를 파일에서 읽어옵니다.
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            found_stocks = json.load(f)
        logging.info(f"{DATA_FILE}에서 {len(found_stocks)}개의 종목 정보를 불러왔습니다.")
    except FileNotFoundError:
        logging.warning(f"{DATA_FILE} 파일을 찾을 수 없습니다. 먼저 데이터 업데이트를 실행하세요.")
        found_stocks = [] # 파일이 없으면 빈 목록을 보여줌
    except json.JSONDecodeError:
        logging.error(f"{DATA_FILE} 파일 형식이 잘못되었습니다.")
        found_stocks = []

    # HTML 파일에 데이터를 넘겨주며 페이지를 생성
    return render_template('index.html', stocks=found_stocks)

if __name__ == '__main__':
    app.run(debug=True)