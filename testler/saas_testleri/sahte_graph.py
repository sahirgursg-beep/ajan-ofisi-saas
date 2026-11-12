"""Testler icin sahte Meta Graph API sunucusu (yerel, internet yok). Her istegi kaydeder.
Yayin: her POST yeni bir kimlik doner; Instagram kaplari hemen FINISHED; DELETE basarili.
OAuth: kod -> kisa anahtar -> uzun anahtar -> iki sayfa."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class SahteGraph:
    def __init__(self):
        self.kayit, self.sayac, self.silinen = [], 1000, []
        self.hata_yollari = {}          # yol parcasi -> (http kodu, meta hata kodu, mesaj)
        sahte = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _yanit(self, veri, kod=200):
                g = json.dumps(veri).encode()
                self.send_response(kod)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(g)))
                self.end_headers()
                self.wfile.write(g)

            def _isle(self, yontem):
                u = urlparse(self.path)
                n = int(self.headers.get("Content-Length") or 0)
                govde = self.rfile.read(n) if n else b""
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                if self.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
                    q.update({k: v[0] for k, v in parse_qs(govde.decode(errors="ignore")).items()})
                sahte.kayit.append((yontem, u.path, q))
                for parca, (kod, mkod, mesaj) in sahte.hata_yollari.items():
                    if parca in u.path:
                        return self._yanit({"error": {"message": mesaj, "code": mkod}}, kod)
                yol = u.path.split("/", 2)[-1] if u.path.count("/") >= 2 else u.path
                if yol.endswith("oauth/access_token"):
                    return self._yanit({"access_token": "UZUN" if q.get("grant_type") else "KISA"})
                if yol.endswith("me/accounts"):
                    return self._yanit({"data": [
                        {"id": "111", "name": "Oak Page", "access_token": "SAYFA111", "tasks": ["CREATE_CONTENT"],
                         "instagram_business_account": {"id": "ig111", "username": "oakember"}},
                        {"id": "222", "name": "Second Page", "access_token": "SAYFA222", "tasks": ["ANALYZE"]},
                        {"id": "333", "name": "Third Page", "access_token": "SAYFA333", "tasks": ["MANAGE"]}]})
                if yontem == "DELETE":
                    sahte.silinen.append(yol)
                    return self._yanit({"success": True})
                if yontem == "GET":
                    f = q.get("fields", "")
                    if "images" in f:
                        return self._yanit({"images": [{"source": "https://cdn.example/x.jpg", "width": 1080}]})
                    if "status_code" in f:
                        return self._yanit({"status_code": "FINISHED"})
                    if "permalink" in f:
                        return self._yanit({"permalink": "https://instagram.example/p/1"})
                    return self._yanit({"data": []})
                sahte.sayac += 1
                i = str(sahte.sayac)
                return self._yanit({"id": i, "post_id": f"p_{i}", "video_id": f"v{i}", "success": True})

            def do_GET(self):
                self._isle("GET")

            def do_POST(self):
                self._isle("POST")

            def do_DELETE(self):
                self._isle("DELETE")

        self.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.adres = f"http://127.0.0.1:{self.sunucu.server_address[1]}"
        threading.Thread(target=self.sunucu.serve_forever, daemon=True).start()

    def kapat(self):
        self.sunucu.shutdown()

    def yollar(self, yontem=None):
        return [p for y, p, _ in self.kayit if yontem in (None, y)]
