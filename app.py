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
        return redirect(f'/?token={token}&expires_in={expires_in}')
    except Exception as e:
        return redirect(f'/?error={str(e)}')

# ── Device code autoryzacja dla monitora cen ──────────────────────────────────

@app.route('/autoryzuj')
def autoryzuj():
    html = '''<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>Autoryzacja Monitora Allegro</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
  .card { background: white; border-radius: 12px; border: 1px solid #e0e0e0; padding: 32px; max-width: 560px; width: 100%; }
  h1 { font-size: 20px; font-weight: 600; margin-bottom: 6px; }
  .sub { font-size: 13px; color: #888; margin-bottom: 24px; }
  .step { background: #f9f9f9; border-radius: 8px; border: 1px solid #e0e0e0; padding: 20px; margin-bottom: 16px; display: none; }
  .step.active { display: block; }
  .step h2 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
  label { font-size: 13px; color: #555; display: block; margin-bottom: 4px; }
  input[type=text], input[type=password] { width: 100%; border: 1px solid #ddd; border-radius: 6px; padding: 8px 10px; font-size: 13px; margin-bottom: 12px; }
  .code-box { background: #1a1a2e; color: #00d4aa; font-family: monospace; font-size: 26px; font-weight: 700; text-align: center; padding: 16px; border-radius: 8px; letter-spacing: 6px; margin: 10px 0; }
  .url-box { background: #f0f0f0; font-family: monospace; font-size: 12px; padding: 8px 12px; border-radius: 6px; word-break: break-all; margin: 8px 0; }
  .token-box { background: #f0faf2; border: 1px solid #a5d6a7; font-family: monospace; font-size: 11px; padding: 10px; border-radius: 6px; word-break: break-all; margin: 6px 0; color: #1b5e20; max-height: 80px; overflow-y: auto; }
  .btn { padding: 9px 18px; border-radius: 6px; border: none; cursor: pointer; font-size: 13px; font-weight: 500; }
  .btn-orange { background: #ff6600; color: white; }
  .btn-green { background: #2e7d32; color: white; }
  .btn-copy { background: #e0e0e0; color: #333; font-size: 12px; padding: 5px 12px; margin-left: 8px; }
  .error { color: #c62828; font-size: 13px; margin-top: 8px; }
  .info { font-size: 13px; color: #555; line-height: 1.6; margin-bottom: 10px; }
  .secret-name { font-family: monospace; font-size: 12px; background: #e0e0e0; padding: 3px 7px; border-radius: 4px; }
  .row { display: flex; align-items: center; margin-bottom: 10px; gap: 8px; }
</style>
</head>
<body>
<div class="card">
  <h1>🔐 Autoryzacja Monitora cen</h1>
  <p class="sub">Jednorazowa konfiguracja — zajmie ~2 minuty</p>

  <div class="step active" id="step1">
    <h2>Krok 1 — Podaj dane aplikacji</h2>
    <p class="info">Wklej Client ID i Client Secret z panelu Allegro Developer. Dane nie są nigdzie zapisywane.</p>
    <label>Client ID</label>
    <input type="text" id="clientId" value="edc40ac7c9e54d4a9878c602499a835a" />
    <label>Client Secret</label>
    <input type="password" id="clientSecret" placeholder="Wklej Client Secret..." />
    <button class="btn btn-orange" onclick="startAuth()">Dalej →</button>
    <div id="err1" class="error"></div>
  </div>

  <div class="step" id="step2">
    <h2>Krok 2 — Zaloguj się na Allegro</h2>
    <p class="info">Twój jednorazowy kod:</p>
    <div class="code-box" id="userCode">------</div>
    <p class="info">Otwórz poniższy link, zaloguj się i wpisz kod:</p>
    <div class="url-box" id="verifyUrl"></div>
    <a id="verifyLink" href="#" target="_blank" class="btn btn-orange" style="display:inline-block;margin-bottom:14px;text-decoration:none;">Otwórz Allegro ↗</a>
    <p class="info">Po wpisaniu kodu na stronie Allegro wróć tutaj i kliknij:</p>
    <button class="btn btn-green" onclick="getToken()">✓ Zalogowałem się</button>
    <div id="err2" class="error"></div>
    <div id="status2" style="font-size:13px;color:#888;margin-top:8px;"></div>
  </div>

  <div class="step" id="step3">
    <h2>✅ Gotowe! Dodaj sekrety do GitHub</h2>
    <p class="info">Wejdź w repozytorium <strong>raporty-cen-Allegro-Zaffiro</strong> → Settings → Secrets and variables → Actions i dodaj:</p>

    <div class="row">
      <span class="secret-name">ALLEGRO_REFRESH_TOKEN</span>
      <button class="btn btn-copy" onclick="copy('rt')">Kopiuj</button>
    </div>
    <div class="token-box" id="rt"></div>

    <div class="row" style="margin-top:12px;">
      <span class="secret-name">ALLEGRO_ACCESS_TOKEN</span>
      <button class="btn btn-copy" onclick="copy('at')">Kopiuj</button>
    </div>
    <div class="token-box" id="at"></div>

    <p style="font-size:12px;color:#888;margin-top:14px;">Po dodaniu sekretów zaktualizuj monitor.py — wyślę Ci nową wersję.</p>
  </div>
</div>

<script>
let deviceCode = '', clientId = '', clientSecret = '';

async function startAuth() {
  clientId = document.getElementById('clientId').value.trim();
  clientSecret = document.getElementById('clientSecret').value.trim();
  document.getElementById('err1').textContent = '';

  if (!clientSecret) {
    document.getElementById('err1').textContent = 'Wpisz Client Secret.';
    return;
  }

  try {
    const resp = await fetch('/device/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: clientId, client_secret: clientSecret })
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    deviceCode = data.device_code;
    document.getElementById('userCode').textContent = data.user_code;
    document.getElementById('verifyUrl').textContent = data.verification_uri_complete || data.verification_uri;
    document.getElementById('verifyLink').href = data.verification_uri_complete || data.verification_uri;

    document.getElementById('step1').classList.remove('active');
    document.getElementById('step2').classList.add('active');
  } catch(e) {
    document.getElementById('err1').textContent = 'Błąd: ' + e.message;
  }
}

async function getToken() {
  document.getElementById('err2').textContent = '';
  document.getElementById('status2').textContent = 'Sprawdzam...';
  try {
    const resp = await fetch('/device/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_id: clientId, client_secret: clientSecret, device_code: deviceCode })
    });
    const data = await resp.json();
    if (data.error === 'authorization_pending') {
      document.getElementById('status2').textContent = '⏳ Jeszcze nie zalogowano. Zaloguj się na Allegro i spróbuj ponownie.';
      return;
    }
    if (data.error) throw new Error(data.error_description || data.error);

    document.getElementById('rt').textContent = data.refresh_token || '(brak)';
    document.getElementById('at').textContent = data.access_token;
    document.getElementById('step2').classList.remove('active');
    document.getElementById('step3').classList.add('active');
  } catch(e) {
    document.getElementById('err2').textContent = 'Błąd: ' + e.message;
    document.getElementById('status2').textContent = '';
  }
}

function copy(id) {
  navigator.clipboard.writeText(document.getElementById(id).textContent)
    .then(() => alert('Skopiowano!'));
}
</script>
</body>
</html>'''
    return html

@app.route('/device/start', methods=['POST'])
def device_start():
    data = request.get_json()
    client_id = data.get('client_id', '')
    client_secret = data.get('client_secret', '')
    try:
        creds = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
        resp = requests.post(
            'https://allegro.pl/auth/oauth/device',
            headers={
                'Authorization': f'Basic {creds}',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data={'client_id': client_id},
            timeout=15
        )
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/device/token', methods=['POST'])
def device_token():
    data = request.get_json()
    client_id = data.get('client_id', '')
    client_secret = data.get('client_secret', '')
    device_code = data.get('device_code', '')
    try:
        creds = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
        resp = requests.post(
            'https://allegro.pl/auth/oauth/token',
            headers={
                'Authorization': f'Basic {creds}',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data={
                'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                'device_code': device_code,
            },
            timeout=15
        )
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Proxy do Allegro API ──────────────────────────────────────────────────────

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
