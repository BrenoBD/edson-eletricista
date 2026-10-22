#!/usr/bin/env python3
"""
Edson Eletricista — servidor leve (estáticos + coletor de eventos + painel).
Só biblioteca padrão. Serve public/, recebe POST /track, e expõe um painel
secreto em /<DASH_SECRET> com os dados agregados (retenção de 14 dias).
"""
import json, os, re, sqlite3, threading, time, mimetypes
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(BASE, 'public')
DASHBOARD_FILE = os.path.join(BASE, 'dashboard.html')
DB_PATH = os.environ.get('DB_PATH', '/data/analytics.db')
SECRET = os.environ.get('DASH_SECRET', 'app-painel-7h2k9x').strip('/')
PORT = int(os.environ.get('PORT', '80'))
RETENTION_DAYS = 14
TZ_OFFSET = -3 * 3600   # America/Sao_Paulo

mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/svg+xml', '.svg')
mimetypes.add_type('application/javascript', '.js')

# ---------------- Banco ----------------
os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute('PRAGMA journal_mode=WAL')
db.execute('''CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL, day TEXT NOT NULL,
  type TEXT NOT NULL, page TEXT NOT NULL, channel TEXT)''')
db.execute('CREATE INDEX IF NOT EXISTS idx_day ON events(day)')
db.commit()
lock = threading.Lock()

def day_of(ts):
    return time.strftime('%Y-%m-%d', time.gmtime(ts + TZ_OFFSET))

def cleanup():
    cutoff = int(time.time()) - RETENTION_DAYS * 86400
    with lock:
        db.execute('DELETE FROM events WHERE ts < ?', (cutoff,))
        db.commit()

def cleanup_loop():
    while True:
        try: cleanup()
        except Exception as e: print('cleanup err:', e, flush=True)
        time.sleep(6 * 3600)
threading.Thread(target=cleanup_loop, daemon=True).start()

def norm_page(p):
    p = (p or '/').split('?')[0].split('#')[0]
    p = re.sub(r'/index\.html$', '/', p)
    p = re.sub(r'\.html$', '', p)
    if len(p) > 1:
        p = p.rstrip('/')
    return p or '/'

# ---------------- HTTP ----------------
class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass

    def reply(self, code, body=b'', ctype='text/plain; charset=utf-8', headers=None):
        if isinstance(body, str): body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_POST(self):
        if urlparse(self.path).path != '/track':
            return self.reply(404, 'not found')
        try:
            n = int(self.headers.get('Content-Length', 0) or 0)
            if n > 2000:
                return self.reply(204)
            data = json.loads(self.rfile.read(n) or b'{}')
        except Exception:
            return self.reply(204)
        t = data.get('type')
        if t not in ('view', 'contact'):
            return self.reply(204)
        page = norm_page(str(data.get('page', ''))[:120])
        channel = data.get('channel') if data.get('channel') in ('whatsapp', 'phone') else None
        ts = int(time.time())
        try:
            with lock:
                db.execute('INSERT INTO events(ts,day,type,page,channel) VALUES(?,?,?,?,?)',
                           (ts, day_of(ts), t, page, channel))
                db.commit()
        except Exception as e:
            print('insert err:', e, flush=True)
        return self.reply(204)

    def do_HEAD(self): self.do_GET()
    def do_GET(self):
        path = urlparse(self.path).path
        if path.rstrip('/') == '/' + SECRET:
            return self.dashboard()
        if path == '/' + SECRET + '/data':
            return self.data()
        return self.static(path)

    def dashboard(self):
        try:
            body = open(DASHBOARD_FILE, 'rb').read()
        except Exception:
            body = b'<!doctype html><h1>Painel indisponivel</h1>'
        self.reply(200, body, 'text/html; charset=utf-8',
                   {'X-Robots-Tag': 'noindex, nofollow', 'Cache-Control': 'no-store'})

    def data(self):
        qs = parse_qs(urlparse(self.path).query)
        try: days = int(qs.get('days', ['7'])[0])
        except Exception: days = 7
        days = max(1, min(days, RETENTION_DAYS))
        now = int(time.time())
        start = day_of(now - (days - 1) * 86400)
        with lock:
            rows = db.execute(
                "SELECT day,type,page,channel,COUNT(*) FROM events WHERE day >= ? "
                "GROUP BY day,type,page,channel", (start,)).fetchall()
        daily = defaultdict(lambda: {'views': 0, 'contacts': 0})
        pages = defaultdict(lambda: {'views': 0, 'contacts': 0, 'whatsapp': 0, 'phone': 0})
        for day, typ, page, channel, c in rows:
            if typ == 'view':
                daily[day]['views'] += c; pages[page]['views'] += c
            else:
                daily[day]['contacts'] += c; pages[page]['contacts'] += c
                if channel in ('whatsapp', 'phone'):
                    pages[page][channel] += c
        series = []
        for i in range(days - 1, -1, -1):
            d = day_of(now - i * 86400)
            series.append({'day': d, 'views': daily[d]['views'], 'contacts': daily[d]['contacts']})
        page_list = []
        for p, v in sorted(pages.items(), key=lambda kv: -kv[1]['views']):
            rate = round(100 * v['contacts'] / v['views'], 1) if v['views'] else 0.0
            page_list.append({'page': p, 'views': v['views'], 'contacts': v['contacts'],
                              'whatsapp': v['whatsapp'], 'phone': v['phone'], 'rate': rate})
        tv = sum(d['views'] for d in series); tc = sum(d['contacts'] for d in series)
        out = {'days': days, 'retention': RETENTION_DAYS, 'daily': series, 'pages': page_list,
               'totals': {'views': tv, 'contacts': tc,
                          'rate': round(100 * tc / tv, 1) if tv else 0.0}}
        self.reply(200, json.dumps(out), 'application/json; charset=utf-8',
                   {'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex'})

    def static(self, path):
        rel = path.lstrip('/') or 'index.html'
        full = os.path.normpath(os.path.join(PUBLIC, rel))
        if not (full == PUBLIC or full.startswith(PUBLIC + os.sep)):
            return self.reply(403, 'forbidden')
        if os.path.isdir(full):
            full = os.path.join(full, 'index.html')
        if not os.path.isfile(full):
            if os.path.isfile(full + '.html'):     # URL limpa: /v2 -> v2.html
                full += '.html'
            else:
                return self.reply(404, '404 - pagina nao encontrada', 'text/html; charset=utf-8')
        ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
        if ctype.startswith('text/') or ctype in ('application/javascript', 'application/json', 'image/svg+xml'):
            ctype += '; charset=utf-8'
        headers = {}
        if re.search(r'\.(css|js|png|jpe?g|gif|svg|webp|ico|woff2?)$', full):
            headers['Cache-Control'] = 'public, max-age=2592000'
        elif full.endswith('.html'):
            headers['Cache-Control'] = 'no-cache'
        try:
            body = open(full, 'rb').read()
        except Exception:
            return self.reply(404, '404')
        self.reply(200, body, ctype, headers)

if __name__ == '__main__':
    print(f'analytics on :{PORT} | public={PUBLIC} | db={DB_PATH} | painel=/{SECRET}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', PORT), H).serve_forever()
