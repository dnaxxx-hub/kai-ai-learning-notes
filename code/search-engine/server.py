"""server.py — HTTP 搜索服务器"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from analyzer import Analyzer
from indexer import InvertedIndex
from searcher import Searcher


class SearchHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理"""

    index = None
    searcher = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path == '/search':
            params = parse_qs(parsed.query)
            query = params.get('q', [''])[0]
            mode = params.get('mode', ['ranking'])[0]
            top_k = int(params.get('top_k', ['10'])[0])

            if not query:
                self._send_json({'error': 'Missing query parameter "q"'}, 400)
                return

            results = self.searcher.search(query, top_k=top_k, mode=mode)
            self._send_json({'query': query, 'mode': mode, 'results': results})
        elif path == '/stats':
            stats = {
                'doc_count': self.index.doc_count,
                'term_count': len(self.index.inverted),
                'documents': list(self.index.documents.keys()),
            }
            self._send_json(stats)
        elif path == '/':
            self._send_html()
        else:
            self._send_json({'error': 'Not found'}, 404)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))

    def _send_html(self):
        html = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Search Engine</title>
<style>
body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }
input { width: 70%; padding: 8px; }
button { padding: 8px 16px; }
.result { margin: 16px 0; border-bottom: 1px solid #eee; padding-bottom: 12px; }
.score { color: #666; font-size: 0.85em; }
.snippet { color: #444; }
</style></head>
<body>
<h1>🔍 Search Engine</h1>
<form id="searchForm">
<input type="text" id="query" placeholder="Search..." />
<button type="submit">Search</button>
<br/>
<label><input type="radio" name="mode" value="ranking" checked/> Ranking</label>
<label><input type="radio" name="mode" value="boolean"/> Boolean</label>
</form>
<div id="results"></div>
<script>
document.getElementById('searchForm').onsubmit = async (e) => {
  e.preventDefault();
  const q = document.getElementById('query').value;
  const mode = document.querySelector('input[name="mode"]:checked').value;
  const res = await fetch('/search?q='+encodeURIComponent(q)+'&mode='+mode);
  const data = await res.json();
  const div = document.getElementById('results');
  if (data.error) { div.innerHTML = '<p>Error: '+data.error+'</p>'; return; }
  div.innerHTML = '<p>Found '+data.results.length+' results for "'+data.query+'" ('+data.mode+')</p>'
    + data.results.map(r => '<div class="result"><strong>'+r.title+'</strong> <span class="score">['+r.score+']</span>'
    + '<div class="snippet">'+r.snippet+'</div></div>').join('');
};
</script>
</body></html>"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        print(f"[Server] {args[0]} {args[1]} {args[2]}")


def create_sample_index():
    """创建示例索引"""
    index = InvertedIndex()
    samples = [
        (1, 'Python Tutorial', 'Python is a programming language. Learn Python for data science and web development. Python tutorial for beginners.'),
        (2, 'Machine Learning Guide', 'Machine learning is a subset of artificial intelligence. Deep learning and neural networks are popular topics.'),
        (3, 'Data Science Basics', 'Data science involves statistics, machine learning, and data analysis. Python is widely used in data science.'),
        (4, 'Deep Learning Tutorial', 'Deep learning uses neural networks with many layers. It is a subset of machine learning.'),
        (5, 'Web Development with Python', 'Build web applications using Python frameworks like Django and Flask. Python makes web development easy.'),
    ]
    for doc_id, title, body in samples:
        index.add_document(str(doc_id), title=title, body=body)
    return index


def run_server(host='localhost', port=8000):
    """启动 HTTP 服务器"""
    SearchHandler.index = create_sample_index()
    SearchHandler.searcher = Searcher(SearchHandler.index)
    server = HTTPServer((host, port), SearchHandler)
    print(f"Search server running at http://{host}:{port}/")
    print(f"Stats: {SearchHandler.index.doc_count} documents, {len(SearchHandler.index.inverted)} terms")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == '__main__':
    run_server()
