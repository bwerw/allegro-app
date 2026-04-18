from flask import Flask, request, Response, send_from_directory
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

ALLEGRO_BASE = 'https://allegro.pl'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/allegro/<path:path>', methods=['GET', 'POST', 'OPTIONS'])
def proxy(path):
    url = f'{ALLEGRO_BASE}/{path}'
    if request.query_string:
        url += '?' + request.query_string.decode()

    headers = {k: v for k, v in request.headers if k in ['Authorization', 'Accept', 'Content-Type']}

    try:
        resp = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            data=request.get_data(),
            timeout=15
        )
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get('Content-Type', 'application/json')
        )
    except Exception as e:
        return {'error': str(e)}, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
