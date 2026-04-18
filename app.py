from flask import Flask, request, Response, send_from_directory, jsonify, redirect
from flask_cors import CORS
import requests
import os
import base64

app = Flask(__name__)
CORS(app)

ALLEGRO_BASE = 'https://allegro.pl'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/oauth/start')
def oauth_start():
    client_id = request.args.get('client_id', '')
    redirect_uri = request.args.get('redirect_uri', '')
    url = (
        f'https://allegro.pl/auth/oauth/authorize'
        f'?response_type=code'
        f'&client_id={client_id}'
        f'&redirect_uri={redirect_uri}'
        f'&scope=allegro:api:sale:offers:read allegro:api:profile:read'
    )
    return redirect(url)

@app.route('/oauth/callback')
def oauth_callback():
    code = request.args.get('code', '')
    client_id = request.args.get('client_id', '')
    client_secret = request.args.get('client_secret', '')
    redirect_uri = request.args.get('redirect_uri', '')

    if not code:
        return send_from_directory(BASE_DIR, 'index.html')

    # Wymień code na token
    try:
        creds = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
        resp = requests.post(
            f'https://allegro.pl/auth/oauth/token'
            f'?grant_type=authorization_code'
            f'&code={code}'
            f'&redirect_uri={redirect_uri}',
            headers={'Authorization': f'Basic {creds}', 'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=15
        )
        data = resp.json()
        token = data.get('access_token', '')
        expires_in = data.get('expires_in', 0)
        # Przekieruj do aplikacji z tokenem
        return redirect(f'/?token={token}&expires_in={expires_in}')
    except Exception as e:
        return redirect(f'/?error={str(e)}')

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
