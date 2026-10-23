"""HTTP behavior for rejected uploads and session restarts.
Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
"""
import http.client
from http.server import ThreadingHTTPServer
import tempfile
import threading
import unittest
from surface_text.server import State, handler_class


class ServerTests(unittest.TestCase):
    def test_rejected_post_closes_unread_body_and_server_stays_usable(self):
        with tempfile.TemporaryDirectory() as d:
            server=ThreadingHTTPServer(('127.0.0.1',0),handler_class(State(d),'valid-token'))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port)
            try:
                connection.request('POST','/api/preview',body=b'{"index":24}',headers={'Content-Type':'application/json'})
                response=connection.getresponse()
                self.assertEqual(response.status,403)
                self.assertEqual(response.getheader('Connection'),'close')
                response.read()
                connection.request('GET','/')
                response=connection.getresponse()
                self.assertEqual(response.status,200)
                self.assertIn('SurfacePin'.encode(),response.read())
                connection.request('GET','/api/status',headers={'X-Surface-Token':'valid-token'})
                response=connection.getresponse()
                self.assertEqual(response.status,200)
                self.assertIn(b'"busy": false',response.read())
            finally:
                connection.close();server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main(verbosity=2)
