import os


# Unlike Mojolicious: the reactor of the test is selected before Pyjo.IOLoop is loaded, as Mojo::Reactor->detect prefers
# Mojo::Reactor::EV where it is installed, and Pyjo.Reactor.detect() prefers Pyjo.Reactor.Asyncio
os.environ['PYJO_REACTOR'] = 'Pyjo.Reactor.Winloop'

import Pyjo.Reactor  # noqa: E402
import Pyjo.Reactor.Asyncio  # noqa: E402
import Pyjo.Reactor.Winloop  # noqa: E402

from Pyjo.Loader import load_class  # noqa: E402
from Pyjo.Test import *  # noqa: E402

import asyncio  # noqa: E402
import signal  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

import winloop  # noqa: E402


def eval_(cb):
    try:
        cb()
    except Exception as e:
        return e


# Shared between subtests, since I/O watchers and timers keep firing across them
readable = writable = 0


def rw_cb(reactor, is_writable):
    global readable, writable
    if is_writable:
        writable += 1
    else:
        readable += 1


with subtest('Instantiation'):
    reactor = Pyjo.Reactor.Winloop.new()
    is_ok(type(reactor), Pyjo.Reactor.Winloop.object, 'right object')
    is_ok(type(Pyjo.Reactor.Winloop.new()), Pyjo.Reactor.Winloop.object, 'right object')
    del reactor
    is_ok(type(Pyjo.Reactor.Winloop.new()), Pyjo.Reactor.Winloop.object, 'right object')
    # Not in Mojolicious: the constructor of Python, as in Pyjoyment, and the reactor of asyncio, which it extends
    is_ok(Pyjo.Reactor.Winloop.Winloop, Pyjo.Reactor.Winloop.object, 'right class')
    is_ok(type(Pyjo.Reactor.Winloop.Winloop()), Pyjo.Reactor.Winloop.object, 'right object')
    ok(issubclass(Pyjo.Reactor.Winloop.object, Pyjo.Reactor.Asyncio.object), 'reactor of asyncio')
    ok(not load_class('Pyjo.IOLoop'), 'use Pyjo.IOLoop')
    reactor = Pyjo.IOLoop.singleton.reactor
    is_ok(type(reactor), Pyjo.Reactor.Winloop.object, 'right object')

with subtest('Make sure it stops automatically when not watching for events'):
    triggered = 0

    def triggered_cb(loop):
        global triggered
        triggered += 1

    Pyjo.IOLoop.next_tick(triggered_cb)
    Pyjo.IOLoop.start()
    ok(triggered, 'reactor waited for one event')
    started = time.time()
    Pyjo.IOLoop.start()
    Pyjo.IOLoop.one_tick()
    ok(time.time() < (started + 10), 'stopped automatically')

with subtest('Listen'):
    listen = socket.create_server(('127.0.0.1', 0), backlog=5)
    port = listen.getsockname()[1]
    reactor.io(listen, rw_cb).watch(listen, False, False).watch(listen, True, True)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(not readable, 'handle is not readable')
    ok(not writable, 'handle is not writable')

with subtest('Connect'):
    client = socket.create_connection(('127.0.0.1', port))
    reactor.timer(1, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(not writable, 'handle is not writable')

with subtest('Accept'):
    server = listen.accept()[0]
    ok(reactor.remove(listen), 'removed')
    ok(not reactor.remove(listen), 'not removed again')
    readable = writable = 0
    reactor.io(client, rw_cb)
    reactor.again(reactor.timer(0.025, lambda reactor: reactor.stop()))
    reactor.start()
    ok(not readable, 'handle is not readable')
    ok(writable, 'handle is writable')
    client.sendall(b'hello!\n')
    time.sleep(1)
    ok(reactor.remove(client), 'removed')
    readable = writable = 0
    reactor.io(server, rw_cb)
    reactor.watch(server, True, False)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(not writable, 'handle is not writable')
    readable = writable = 0
    reactor.watch(server, True, True)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(writable, 'handle is writable')
    readable = writable = 0
    reactor.watch(server, False, False)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(not readable, 'handle is not readable')
    ok(not writable, 'handle is not writable')
    readable = writable = 0
    reactor.watch(server, True, False)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(not writable, 'handle is not writable')
    readable = writable = 0
    reactor.io(server, rw_cb)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable')
    ok(writable, 'handle is writable')

with subtest('Timers'):
    timer = recurring = 0

    def timer_cb(reactor):
        global timer
        timer += 1

    def recurring_cb(reactor):
        global recurring
        recurring += 1

    reactor.timer(0, timer_cb)
    ok(reactor.remove(reactor.timer(0, timer_cb)), 'removed')
    id = reactor.recurring(0, recurring_cb)
    readable = writable = 0
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(timer, 'timer was triggered')
    ok(recurring, 'recurring was triggered')
    done = False
    readable = writable = timer = recurring = 0

    def done_cb(reactor):
        global done
        done = reactor.is_running

    reactor.timer(0.025, done_cb)
    while not done:
        reactor.one_tick()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(not timer, 'timer was not triggered')
    ok(recurring, 'recurring was triggered again')
    readable = writable = timer = recurring = 0
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(not timer, 'timer was not triggered')
    ok(recurring, 'recurring was triggered again')
    ok(reactor.remove(id), 'removed')
    ok(not reactor.remove(id), 'not removed again')
    readable = writable = timer = recurring = 0
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(not timer, 'timer was not triggered')
    ok(not recurring, 'recurring was not triggered again')
    readable = writable = timer = recurring = 0
    next_tick = 0

    def next_tick_cb(reactor):
        global next_tick
        next_tick += 1

    is_ok(reactor.next_tick(next_tick_cb), None, 'returned None')
    id = reactor.recurring(0, recurring_cb)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(readable, 'handle is readable again')
    ok(writable, 'handle is writable again')
    ok(not timer, 'timer was not triggered')
    ok(recurring, 'recurring was triggered again')
    ok(next_tick, 'next tick was triggered')

with subtest('Reset'):

    def reset_failed_cb(reactor):
        raise Exception('Reset failed')

    reactor.next_tick(reset_failed_cb)
    reactor.reset()
    readable = writable = recurring = 0
    reactor.next_tick(lambda reactor: reactor.stop())
    reactor.start()
    ok(not readable, 'io event was not triggered again')
    ok(not writable, 'io event was not triggered again')
    ok(not recurring, 'recurring was not triggered again')
    reactor2 = Pyjo.Reactor.Winloop.new()
    is_ok(type(reactor2), Pyjo.Reactor.Winloop.object, 'right object')

with subtest('Ordered next_tick'):
    result = []
    for i in range(1, 11):
        reactor.next_tick(lambda reactor, i=i: result.append(i))
    reactor.start()
    is_deeply_ok(result, list(range(1, 11)), 'right result')

with subtest('Reset while watchers are active'):
    writable = 0

    def reset_cb(reactor, is_writable):
        global writable
        writable += 1
        reactor.reset()

    for handle in (client, server):
        reactor.io(handle, reset_cb).watch(handle, False, True)
    reactor.start()
    is_ok(writable, 1, 'only one handle was writable')
    client.close()
    server.close()

with subtest('Concurrent reactors'):
    timer = 0
    reactor.recurring(0, timer_cb)
    timer2 = 0

    def timer2_cb(reactor):
        global timer2
        timer2 += 1

    reactor2.recurring(0, timer2_cb)
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(timer, 'timer was triggered')
    ok(not timer2, 'timer was not triggered')
    timer = timer2 = 0
    reactor2.timer(0.025, lambda reactor: reactor.stop())
    reactor2.start()
    ok(not timer, 'timer was not triggered')
    ok(timer2, 'timer was triggered')
    timer = timer2 = 0
    reactor.timer(0.025, lambda reactor: reactor.stop())
    reactor.start()
    ok(timer, 'timer was triggered')
    ok(not timer2, 'timer was not triggered')
    timer = timer2 = 0
    reactor2.timer(0.025, lambda reactor: reactor.stop())
    reactor2.start()
    ok(not timer, 'timer was not triggered')
    ok(timer2, 'timer was triggered')
    reactor.reset()

with subtest('Restart timer'):
    single = pair = last = 0

    def single_cb(reactor):
        global single
        single += 1

    def one_cb(reactor):
        global pair, last
        if single and pair:
            last += 1
        pair += 1
        reactor.stop() if pair > 1 else reactor.again(two)

    def two_cb(reactor):
        global pair, last
        if single and pair:
            last += 1
        pair += 1
        reactor.stop() if pair > 1 else reactor.again(one)

    reactor.timer(0.025, single_cb)
    one = reactor.timer(0.025, one_cb)
    two = reactor.timer(0.025, two_cb)
    reactor.start()
    is_ok(pair, 2, 'timer pair was triggered')
    ok(single, 'single timer was triggered')
    ok(last, 'timers were triggered in the right order')

with subtest('Reset timer'):
    before = time.monotonic()
    after = None
    again = 0

    def after_cb(reactor):
        global after
        after = time.monotonic()

    def again_cb(reactor):
        global again
        again += 1
        if again > 3:
            reactor.remove(two)

    def restart_cb(reactor):
        reactor.again(one, 0.025)
        reactor.again(two, 0.025)

    one = reactor.timer(300, after_cb)
    two = reactor.recurring(300, again_cb)
    reactor.timer(0.025, restart_cb)
    reactor.start()
    ok(after, 'timer was triggered')
    ok((after - before) < 200, 'less than 200 seconds')
    is_ok(again, 4, 'recurring timer triggered four times')

with subtest('Restart inactive timer'):
    id = reactor.timer(0, lambda reactor: None)
    ok(reactor.remove(id), 'removed')
    err = eval_(lambda: reactor.again(id))
    like_ok(str(err), r'Timer not active', 'right error')

with subtest('Change inactive I/O watcher'):
    ok(not reactor.remove(listen), 'not removed again')
    err = eval_(lambda: reactor.watch(listen, True, True))
    like_ok(str(err), r'I/O watcher not active', 'right error')
    listen.close()

with subtest('Error'):
    err = None

    def error_cb(reactor, e):
        global err
        reactor.stop()
        err = e

    def die_cb(reactor):
        raise Exception('works!\n')

    reactor.unsubscribe('error').on('error', error_cb)
    reactor.timer(0, die_cb)
    reactor.start()
    like_ok(str(err), r'works!', 'right error')

    # Not in Mojolicious: the arguments of a callback, which Perl does not check, as in Pyjo.Reactor.Asyncio
    reactor.timer(0, lambda: None)
    reactor.start()
    like_ok(
        str(err),
        r'takes 0 positional arguments but 1 was given: the callbacks of a reactor get the reactor first',
        'hint',
    )

with subtest('Reset events'):
    reactor.on('error', lambda reactor, err: None)
    ok(reactor.has_subscribers('error'), 'has subscribers')
    reactor.reset()
    ok(not reactor.has_subscribers('error'), 'no subscribers')

with subtest('Recursion'):
    timer = 0

    def recursion_cb(reactor):
        global timer
        timer += 1
        reactor.one_tick()

    reactor = Pyjo.Reactor.Winloop.new()
    reactor.timer(0, recursion_cb)
    reactor.one_tick()
    is_ok(timer, 1, 'timer was triggered once')

with subtest('Detection'):
    is_ok(Pyjo.Reactor.object.detect(), 'Pyjo.Reactor.Winloop', 'right class')

with subtest('Reactor in control'):
    is_ok(type(Pyjo.IOLoop.singleton.reactor), Pyjo.Reactor.Winloop.object, 'right object')
    ok(not Pyjo.IOLoop.is_running(), 'loop is not running')
    buffer = b''
    server_err = server_running = client_err = client_running = None

    def server_cb(loop, stream, cid):
        global server_err, server_running
        stream.write(b'test', lambda stream: stream.write(b'321'))
        server_running = Pyjo.IOLoop.is_running()
        server_err = eval_(lambda: Pyjo.IOLoop.start())

    id = Pyjo.IOLoop.server(server_cb, address='127.0.0.1')
    port = Pyjo.IOLoop.acceptor(id).port

    def client_cb(loop, err, stream):
        global client_err, client_running

        def read_cb(stream, chunk):
            global buffer
            buffer += chunk
            if buffer != b'test321':
                return
            Pyjo.IOLoop.singleton.reactor.stop()

        stream.on('read', read_cb)
        client_running = Pyjo.IOLoop.is_running()
        client_err = eval_(lambda: Pyjo.IOLoop.start())

    Pyjo.IOLoop.client(client_cb, port=port)
    Pyjo.IOLoop.singleton.reactor.start()
    ok(not Pyjo.IOLoop.is_running(), 'loop is not running')
    like_ok(str(server_err), r'^Pyjo.IOLoop already running', 'right error')
    like_ok(str(client_err), r'^Pyjo.IOLoop already running', 'right error')
    ok(server_running, 'loop is running')
    ok(client_running, 'loop is running')

# Left out from Mojolicious: the abstract methods of Mojo::Reactor, which t/Pyjo/Reactor_Asyncio.py of Pyjoyment tests

# Not in Mojolicious: a callback of next_tick from a signal handler, which Python runs in the middle of what the reactor
# does, as the servers stop gracefully, with enough timers that the handler interrupts the reactor while it handles
# them, as in Pyjo.Reactor.Asyncio
with subtest('next_tick from a signal handler'):
    if not hasattr(signal, 'setitimer'):
        plan(skip_all='signal.setitimer is required')
    reactor = Pyjo.Reactor.Winloop.new()
    for _ in range(100000):
        reactor.timer(10, lambda reactor: None)
    ticks = []
    handler = signal.signal(signal.SIGALRM, lambda signum, frame: reactor.next_tick(lambda reactor: ticks.append(1)))
    signal.setitimer(signal.ITIMER_REAL, 0.001, 0.001)
    reactor.timer(0.3, lambda reactor: reactor.stop())
    try:
        err = eval_(lambda: reactor.start())
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)
    is_ok(err, None, 'no error')
    ok(ticks, 'callbacks of the signal handler')
    reactor.reset()
    reactor.close()


# Not in Mojolicious: the loop of Winloop, which is what the reactor adds to Pyjo.Reactor.Asyncio
with subtest('Loop of its own of Winloop'):
    with Pyjo.Reactor.Winloop.new() as reactor:
        loop = reactor.loop
        ok(isinstance(loop, winloop.Loop), 'loop of Winloop')
        ok(isinstance(loop, asyncio.AbstractEventLoop), 'loop of asyncio')
        is_ok(reactor.loop, loop, 'same loop')
        fired = []
        reactor.timer(
            0, lambda reactor: (fired.append(isinstance(asyncio.get_running_loop(), winloop.Loop)), reactor.stop())
        )
        reactor.start()
        is_deeply_ok(fired, [True], 'timer in the loop of Winloop')
    ok(loop.is_closed(), 'loop closed at the end of the block')
    with Pyjo.Reactor.Asyncio.new() as reactor:
        ok(not isinstance(reactor.loop, winloop.Loop), 'the reactor of asyncio keeps the loop of asyncio')

with subtest('Loop that the reactor is given'):
    loop = asyncio.SelectorEventLoop()
    reactor = Pyjo.Reactor.Winloop.new(loop=loop)
    is_ok(reactor.loop, loop, 'loop of asyncio that it is given')
    reactor.close()
    ok(not loop.is_closed(), 'loop that it is given not closed')
    loop.close()

# As inside an ASGI server, which runs the loop itself: the reactor takes the loop that is running, of asyncio or of
# Winloop, where the loop of asyncio is a SelectorEventLoop, as the ProactorEventLoop of Windows cannot watch handles
with subtest('Loop that is running'):

    async def running():
        reactor = Pyjo.Reactor.Winloop.new()
        return reactor.loop is asyncio.get_running_loop(), isinstance(reactor.loop, winloop.Loop)

    is_deeply_ok(
        asyncio.run(running(), loop_factory=asyncio.SelectorEventLoop),
        (True, False),
        'loop of asyncio that is running, not one of Winloop',
    )
    is_deeply_ok(winloop.run(running()), (True, True), 'loop of Winloop that is running')

with subtest('Coroutine on the loop of Winloop'):

    async def coroutine():
        await asyncio.sleep(0.01)
        return isinstance(asyncio.get_running_loop(), winloop.Loop)

    with Pyjo.Reactor.Winloop.new() as reactor:
        result = []
        reactor.run_coroutine(
            coroutine(),
            lambda value: (result.append(value), reactor.stop()),
            lambda err: (result.append(err), reactor.stop()),
        )
        reactor.start()
        is_deeply_ok(result, [True], 'coroutine of asyncio on the loop of Winloop')

with subtest('Threshold of a slow callback'):
    os.environ['PYJO_ASYNCIO_SLOW_CALLBACK'] = '5'
    try:
        with Pyjo.Reactor.Winloop.new() as reactor:
            is_ok(reactor.loop.slow_callback_duration, 5.0, 'from PYJO_ASYNCIO_SLOW_CALLBACK')
    finally:
        del os.environ['PYJO_ASYNCIO_SLOW_CALLBACK']

# Left out from Pyjo-Reactor-Uvloop: the child of a fork, which Windows does not have, and the wakeup fd of a program,
# which Winloop replaces with its own while it runs, as no server of Pyjoyment on Windows waits for it with the reactor

# Not in Mojolicious: a signal that comes while the loop waits, as the Ctrl-C or Ctrl-Break that stops a server, wakes it
# up, through the wakeup fd of Winloop, and its handler of Python runs, which stops the reactor; the signal is raised in
# another thread, as a handler of Windows runs, so that the main thread waits for it in the loop
with subtest('Signal while the loop waits'):
    noted = []

    def note(signum, frame):
        noted.append(signum)
        reactor.stop()

    handler = signal.signal(signal.SIGINT, note)
    try:
        with Pyjo.Reactor.Winloop.new() as reactor:
            reactor.timer(10, lambda reactor: reactor.stop())
            raiser = threading.Timer(0.1, signal.raise_signal, (signal.SIGINT,))
            raiser.start()
            started = time.monotonic()
            reactor.start()
            raiser.join()
            ok(time.monotonic() - started < 5, 'woken up before the timer')
    finally:
        signal.signal(signal.SIGINT, handler)
    is_deeply_ok(noted, [signal.SIGINT], 'handler of the signal')
    is_ok(signal.set_wakeup_fd(-1), -1, 'wakeup fd of Winloop removed at the end of the run')

# Not in Mojolicious: an async generator that the end of another one frees, whose finalizer Winloop calls while CPython
# clears the frame, in the debug mode of asyncio, which crashed the interpreter with uvloop, so in a process of its own
with subtest('Finalizer of an async generator in the debug mode'):
    code = """
import Pyjo.Reactor.Winloop


async def numbers():
    for i in range(10):
        yield i


async def head(n):
    it = numbers()
    while n > 0:
        n -= 1
        yield await anext(it)


async def main():
    return [[e async for e in head(2)] for _ in range(100)][-1]


reactor = Pyjo.Reactor.Winloop.new()
reactor.loop.set_debug(True)
result = []
reactor.run_coroutine(main(), lambda value: (result.append(value), reactor.stop()), lambda err: (result.append(err), reactor.stop()))
reactor.start()
print(result)
"""
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=60)
    is_ok(result.returncode, 0, 'no crash')
    is_ok(result.stdout, '[[0, 1]]\n', 'right result')

# Not in Mojolicious: after stop, the loop of Winloop polls once more, which would call a writer that stops it again in
# the same run, where the loop of asyncio ends after the callbacks of its select
with subtest('Stop in a callback of I/O'):
    a, b = socket.socketpair()
    with Pyjo.Reactor.Winloop.new() as reactor:
        calls = []

        def stopping(reactor, writable):
            calls.append(writable)
            reactor.stop()

        reactor.io(a, stopping).watch(a, False, True)
        reactor.start()
        is_deeply_ok(calls, [True], 'one event before the stop')
        reactor.start()
        is_deeply_ok(calls, [True, True], 'one event in the next run')
        calls.clear()
        reactor.recurring(0, lambda reactor: None)
        for _ in range(3):
            reactor.one_tick()
        ok(len(calls) >= 1, 'no starving of I/O by a timer of no time in one_tick')
        reactor.remove(a)
    a.close()
    b.close()

# Not in Mojolicious: libuv of Windows reports the reset of a socket as an event, and keeps watching it, so its writer is
# called for as long as the error lasts, as with the loop of asyncio, where libuv of Linux calls it once
with subtest('Writer of a socket whose peer has closed it'):
    a, b = socket.socketpair()
    a.setblocking(False)
    with Pyjo.Reactor.Winloop.new() as reactor:
        calls = []
        errors = []

        def writer(reactor, writable):
            calls.append(writable)
            if len(calls) == 1:
                b.close()
            try:
                a.send(b'x')
            except OSError as e:
                errors.append(e)

        reactor.io(a, writer).watch(a, False, True)
        reactor.timer(0.1, lambda reactor: reactor.stop())
        reactor.start()
        ok(errors, 'error of the socket')
        ok(len(errors) > 1, 'writer called again after the error')
        reactor.remove(a)
    a.close()

# Not in Mojolicious: libuv of Windows polls a socket with an exclusive request of AFD, which ends the request of another
# loop for the same socket, which polls it again, in a busy loop; the loops of reactors in threads that watch one socket,
# as the workers of Pyjo.Server.Prethread watch the listen sockets of the manager, poll it one at a time, in turn
with subtest('A socket that reactors in threads watch'):
    server = socket.create_server(('127.0.0.1', 0))
    server.setblocking(False)
    port = server.getsockname()[1]
    accepted = [0, 0, 0, 0]
    reactors = []
    ready = threading.Barrier(5)

    def serve(n):
        with Pyjo.Reactor.Winloop.new() as reactor:

            def accept(reactor, writable):
                try:
                    conn, _ = server.accept()
                except BlockingIOError:
                    return
                accepted[n] += 1
                conn.close()

            reactor.io(server, accept).watch(server, True, False)
            reactors.append(reactor)
            reactor.next_tick(lambda reactor: ready.wait())
            reactor.start()
            reactor.remove(server)

    threads = [threading.Thread(target=serve, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    ready.wait()
    cpu, started = time.process_time(), time.monotonic()
    time.sleep(1)
    cpu, elapsed = time.process_time() - cpu, time.monotonic() - started
    ok(cpu < elapsed / 2, 'idle loops do not poll the socket in a busy loop')
    for _ in range(40):
        with socket.create_connection(('127.0.0.1', port)) as client:
            client.recv(1)
    is_ok(sum(accepted), 40, 'all connections accepted')
    ok(all(accepted), 'by every reactor in turn')
    for reactor in reactors:
        reactor.loop.call_soon_threadsafe(reactor.stop)
    for thread in threads:
        thread.join(10)
    ok(not any(thread.is_alive() for thread in threads), 'reactors stopped')
    server.close()

done_testing()
