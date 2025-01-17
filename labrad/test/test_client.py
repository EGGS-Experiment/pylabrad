import pytest
import contextlib

import labrad
from labrad import types as T
from labrad.util import syncRunServer
from labrad.test.server.test_server import PythonTestServer

TEST_STR = 'this is a test, this is only a test'


class TestClient:

    def setup_class(cls):
        cls.exit_stack = contextlib.ExitStack()
        cls.exit_stack.enter_context(syncRunServer(PythonTestServer()))
        cls.cxn = cls.exit_stack.enter_context(labrad.connect())

    def teardown_class(cls):
        cls.exit_stack.close()

    def _get_manager(self):
        assert hasattr(self.cxn, 'manager')
        return self.cxn.manager

    def _get_tester(self):
        assert hasattr(self.cxn, 'python_test_server')
        return self.cxn.python_test_server

    def test_connection(self):
        servers = self.cxn.servers
        assert len(servers.keys()) > 0
        assert 'manager' in servers
        assert 'python_test_server' in servers

        self._get_manager()
        self._get_tester()

        self._get_manager()
        self._get_tester()

    def test_server(self):
        pts = self._get_tester()

        # make sure we can access the setting by both allowed methods
        assert hasattr(pts, 'echo')
        assert 'echo' in pts.settings

        # single setting, named explicitly
        resp = pts.echo(TEST_STR)
        assert resp == TEST_STR

        resp = pts.echo(T.Value(15.0, 's'))
        assert resp['s'] == 15.0
        assert resp.unit.name == 's'

        # single setting with the name looked up
        resp = pts.settings['echo']([1, 2, 3, 4])
        assert len(resp) == 4

        # single setting with delayed response
        resp = pts.echo.future(TEST_STR)
        resp = resp.result()
        assert resp == TEST_STR

        # allow calling with wait=False for backwards compatibility
        resp = pts.echo(TEST_STR, wait=False)
        resp = resp.result()
        assert resp == TEST_STR

    def test_compound_packet(self):
        pts = self._get_tester()

        assert hasattr(pts, 'packet')

        # make a simple packet and check the various methods of getting
        # data out of it
        pkt = pts.packet()
        resp = pkt.echo(1).echo(2).settings['echo'](3).send()
        assert hasattr(resp, 'echo')
        assert len(resp.echo) == 3
        assert 'echo' in resp.settings
        assert len(resp.settings['echo']) == 3
        assert len(resp['echo']) == 3

        # test using keys to refer to parts of a packet
        pkt2 = pts.packet()
        resp = pkt2.echo(1, key='one')\
                   .echo_delay(T.Value(0.1, 's'))\
                   .delayed_echo('blah', key='two')\
                   .send()
        assert hasattr(resp, 'one')
        assert 'one' in resp.settings
        assert resp['one'] == 1
        assert not hasattr(resp, 'echo_word')
        assert resp.two == 'blah'

        # test packet mutation by key
        pkt2['two'] = TEST_STR
        resp = pkt2.send()
        assert resp.two == TEST_STR

        # send packet asynchronously
        resp = pkt2.send_future()
        resp = resp.result()
        assert resp.two == TEST_STR

        # allow sending with wait=False for backwards compatibility
        resp = pkt2.send(wait=False)
        resp = resp.result()
        assert resp.two == TEST_STR

    def test_tuple_keys(self):
        # allow the use of tuples as packet keys
        pts = self._get_tester()

        p = pts.packet()
        p.echo(1, key='a')
        p.echo(2, key=(1, 2))
        r = repr(p)
        s = str(p)
        resp = p.send()
        assert resp.a == 1
        assert resp['a'] == 1
        assert resp[(1, 2)] == 2

    def test_exceptions(self):
        pts = self._get_tester()

        pts.echo_delay(T.Value(0.1, 's'))
        with pytest.raises(Exception):
            pts.exc_in_handler()
        with pytest.raises(Exception):
            pts.exc_in_subfunction()
        with pytest.raises(Exception):
            pts.exc_in_deferred()
        with pytest.raises(Exception):
            pts.exc_in_errback()
        with pytest.raises(Exception):
            pts.exc_in_inlinecallback()

    def test_context_wrappers(self):
        cxn1 = self.cxn()
        cxn2 = self.cxn()

        pts1 = cxn1.python_test_server
        pts2 = cxn2.python_test_server
        pts3 = cxn1.python_test_server()
        pts4 = pts2()

        pts1.set('1', 1)
        pts2.set('2', 2)
        pts3.set('3', 3)
        pts4.set('4', 4)

        assert pts1.keys() == ['1']
        assert pts2.keys() == ['2']
        assert pts3.keys() == ['3']
        assert pts4.keys() == ['4']

    def test_server_calls(self):
        """Make sure that server settings can call other settings directly.
        """
        cxn = self.cxn()

        ts = cxn.python_test_server

        ts.set_reversed("bar", "foo")
        assert ts.get("foo") == "bar"

        ts.echo_delay(T.Value(0.1, 's'))
        assert ts.delayed_echo_wrapper(1) == 1

    def test_spawn(self):
        cxn1 = self.cxn()

        # Can spawn from active client.
        with cxn1.spawn() as cxn2:
            assert cxn2.connected
            cxn2.manager.servers()

        # Can spawn from client after disconnect
        assert not cxn2.connected
        with cxn2.spawn() as cxn3:
            assert cxn3.connected
            cxn3.manager.servers()
