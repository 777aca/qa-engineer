"""隔离的本机页面；没有真实账号、支付接口或外部请求。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def site():
    state = {"posts": 0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            state["posts"] += 1
            self.send_response(200)
            self.end_headers()

        def do_GET(self):
            if self.path.startswith("/broken"):
                self.send_response(503)
                self.end_headers()
                return
            routes = {
                "/good": '''<form><label for="email">邮箱</label><input id="email" type="email" required>
                    <label for="password">密码</label><input id="password" type="password" required>
                    <button disabled>登录</button></form><img alt="" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E">''',
                "/native": '''<form><label for="email">邮箱</label><input id="email" type="email" required>
                    <label for="password">密码</label><input id="password" type="password" required><button>登录</button></form>''',
                "/images": '''<img src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E">''',
                "/blank": "<p>简洁但正常的页面</p>",
                "/post": '''<p>API 页面</p><script>fetch('/write', {method:'POST'}).catch(()=>{});</script>''',
                "/auth": '''<p id="auth"></p><script>document.querySelector('#auth').textContent=localStorage.getItem('auth_token')?'已登录':'未登录';</script>''',
                "/leak": '''<p>测试数据</p><script>localStorage.setItem('password','FAKE-CREDENTIAL');console.log('password=FAKE-CREDENTIAL');</script>''',
                "/app": (Path(__file__).parent / "fixtures" / "app.html").read_text(encoding="utf-8"),
            }
            body = routes.get(self.path.split("?")[0], "<p>测试页面</p>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(("<!doctype html><html><head><title>本机测试</title></head><body>" + body + "</body></html>").encode("utf-8"))

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", state
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as pw:
        instance = pw.chromium.launch(headless=True)
        yield instance
        instance.close()
