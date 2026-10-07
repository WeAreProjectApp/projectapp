import socket
from threading import Event, Thread
from urllib.request import urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

from accounts.tests.issue_browser_server import ThreadedWSGIServer


def test_server_accepts_request_while_idle_connection_is_open():
    accepted = Event()

    class ObservableHandler(WSGIRequestHandler):
        def handle(self):
            accepted.set()
            return super().handle()

        def log_message(self, format, *args):
            pass

    def application(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'ready']

    with make_server(
        '127.0.0.1', 0, application,
        server_class=ThreadedWSGIServer, handler_class=ObservableHandler,
    ) as server:
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        idle_connection = socket.create_connection(server.server_address, timeout=1)
        try:
            assert accepted.wait(timeout=1)
            with urlopen(
                f'http://127.0.0.1:{server.server_port}/', timeout=2,
            ) as response:
                assert response.read() == b'ready'
        finally:
            idle_connection.close()
            server.shutdown()
            server_thread.join(timeout=2)

    assert not server_thread.is_alive()
