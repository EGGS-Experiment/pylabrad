import queue
import random

import pytest

import labrad
from labrad import util
from labrad.server import LabradServer, ThreadedServer, setting


def test_server_expire_context_method_is_called():
    """Ensure that server's expireContext method is called when client disconnects."""
    q = queue.Queue()

    class TestServer(LabradServer):
        name = "TestServer"

        def expireContext(self, c):
            q.put(c.ID)

        @setting(100)
        def echo(self, c, data):
            return data

    with util.syncRunServer(TestServer()):
        with labrad.connect() as cxn:
            # create a random context owned by this connection
            request_context = (cxn.ID, random.randint(0, 2**32-1))
            cxn.testserver.echo('hello, world!', context=request_context)
        expired_context = q.get(block=True, timeout=1)
        assert expired_context == request_context


def test_threaded_server_client_can_be_spawned():
    class TestServer(ThreadedServer):
        name = "TestServer"

        @setting(100)
        def spawn_call(self, c, server, setting, data):
            with self.client.spawn() as cxn:
                return cxn[server][setting](data)

    with util.syncRunServer(TestServer()):
        with labrad.connect() as cxn:
            result = cxn.testserver.spawn_call('Manager', 'Echo', 'woot!')
            assert result == 'woot!'


def test_server_init_failure_is_propagated():

    class InitError(Exception):
        pass

    class DyingServer(LabradServer):
        name = "Dying Server"
        def initServer(self):
            raise InitError()

    with pytest.raises(InitError):
        with util.syncRunServer(DyingServer()):
            pass


if __name__ == '__main__':
    pytest.main(['-v', __file__])
