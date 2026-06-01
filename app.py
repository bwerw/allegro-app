from flask import Flask, request, Response, send_from_directory, jsonify, redirect
from flask_cors import CORS
import requests
import re
import os
import base64

app = Flask(__name__)
CORS(app)

ALLEGRO_BASE = 'https://allegro.pl'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SELLER_LOGIN = 'Zaffiro_Official'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

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

# ── Device code autoryzacja ───────────────────────────────────────────────────

@app.route('/autoryzuj')
def autoryzuj():
    return send_from_directory(BASE_DIR, 'autoryzuj.html')

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

# ── Sprawdzanie cen — główny endpoint dla monitora ────────────────────────────

@app.route('/api/ceny', methods=['POST'])
def api_ceny():
    """
    Przyjmuje listę URL-i produktów Allegro,
    pobiera strony /oferty-produktu/ i zwraca ceny.
    Body: { "urls": ["https://allegro.pl/produkt/..."] }
    """
    data = request.get_json()
    urls = data.get('urls', [])
    results = []

    for url in urls[:50]:  # max 50 na raz
        offers_url = get_offers_url(url)
        if not offers_url:
            results.append({'url': url, 'error': 'Nie rozpoznano URL'})
            continue
        try:
            result = fetch_prices(offers_url)
            result['url'] = url
            result['offers_url'] = offers_url
            results.append(result)
        except Exception as e:
            results.append({'url': url, 'error': str(e)})

    return jsonify(results)


@app.route('/api/linki-sprzedawcy')
def api_linki_sprzedawcy():
    """
    Pobiera linki do wszystkich produktów sprzedawcy Zaffiro_Official.
    Parametr: ?strona=1
    """
    strona = request.args.get('strona', '1')
    try:
        page_url = f'https://allegro.pl/uzytkownik/{SELLER_LOGIN}?p={strona}'
        resp = requests.get(page_url, headers=HEADERS, timeout=20)
        html = resp.text

        # Wyciągnij linki do produktów
        links = re.findall(
            r'href="(https://allegro\.pl/(?:produkt|oferty-produktu)/[^"?]+)"',
            html
        )
        links = list(dict.fromkeys(links))  # deduplikacja

        # Sprawdź czy jest następna strona
        has_next = f'p={int(strona)+1}' in html or 'następna' in html.lower()

        # Całkowita liczba ofert
        total_match = re.search(r'(\d+)\s+ofert', html)
        total = int(total_match.group(1)) if total_match else 0

        return jsonify({
            'strona': int(strona),
            'linki': links,
            'has_next': has_next,
            'total': total,
            'status': resp.status_code,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_offers_url(url):
    """Zwraca URL strony /oferty-produktu/ dla danego produktu."""
    m = re.search(r'/produkt/([^?#]+)', url)
    if m:
        return f'https://allegro.pl/oferty-produktu/{m.group(1)}'
    m = re.search(r'/oferty-produktu/([^?#]+)', url)
    if m:
        return f'https://allegro.pl/oferty-produktu/{m.group(1)}'
    return None


def fetch_prices(offers_url):
    """Pobiera stronę ofert i parsuje ceny."""
    resp = requests.get(offers_url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        raise Exception(f'HTTP {resp.status_code}')
    html = resp.text

    # Nazwa produktu
    name_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    product_name = re.sub(r'<[^>]+>', '', name_match.group(1)).strip() if name_match else 'Nieznany'

    # Parsuj oferty — dziel HTML po offerId
    offers = []
    sections = re.split(r'(?=offerId=\d+)', html)

    for section in sections:
        oid = re.search(r'offerId=(\d+)', section)
        if not oid:
            continue
        offer_id = oid.group(1)

        price_m = re.search(r'(\d[\d\s]*[,\.]\d{2})\s*zł', section)
        if not price_m:
            continue
        try:
            price = float(price_m.group(1).replace('\xa0','').replace(' ','').replace(',','.'))
        except ValueError:
            continue

        # Sprzedawca
        seller_m = re.search(r'(?:od\s+|">)([A-Za-z0-9_\-\.]{3,50})(?:\s*<|\s*Poleca|\s*\d+\s*ocen)', section)
        seller = seller_m.group(1).strip() if seller_m else ''

        offers.append({
            'offer_id': offer_id,
            'price': price,
            'seller': seller,
            'offer_url': f'https://allegro.pl/oferta/{offer_id}',
        })

    # Deduplikuj i sortuj
    seen = set()
    unique = []
    for o in offers:
        if o['offer_id'] not in seen:
            seen.add(o['offer_id'])
            unique.append(o)
    unique.sort(key=lambda x: x['price'])

    # Cena Zaffiro
    zaffiro_price = None
    for o in unique:
        if SELLER_LOGIN.lower() in o['seller'].lower() or 'zaffiro' in o['seller'].lower():
            zaffiro_price = o['price']
            break

    lowest = unique[0] if unique else None

    return {
        'product_name': product_name,
        'zaffiro_price': zaffiro_price,
        'lowest_price': lowest['price'] if lowest else None,
        'lowest_seller': lowest['seller'] if lowest else '',
        'lowest_offer_url': lowest['offer_url'] if lowest else '',
        'offer_count': len(unique),
    }

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
