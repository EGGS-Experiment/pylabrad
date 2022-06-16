import threading

import pytest

from labrad import util
from labrad.server import LabradServer


def test_sync_run_server():
    """Ensure that syncRunServer runs the stopServer method on shutdown."""
    event = threading.Event()

    class TestServer(LabradServer):
        name = "TestServer"

        def stopServer(self):
            event.set()

    server = TestServer()
    with util.syncRunServer(server):
        pass
    if not event.wait(0.5):
        raise Exception('event not set in stopServer method')

if __name__ == '__main__':
    pytest.main(['-v', __file__])
