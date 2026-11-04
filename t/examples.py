from Pyjo.Test import *

import http.client
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time


# The examples, on the port 3000 replaced by a free one, each in a process of its own
EXAMPLES = os.path.join(os.path.dirname(__file__), '..', 'examples')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def get(port, deadline):
    while True:
        try:
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            try:
                conn.request('GET', '/')
                res = conn.getresponse()
                return res.status, res.read()
            finally:
                conn.close()
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


with subtest('hello_world_winloop.py'), tempfile.TemporaryDirectory() as dir:
    with open(os.path.join(EXAMPLES, 'hello_world_winloop.py')) as file:
        source = file.read()
    port = free_port()
    script = os.path.join(dir, 'hello_world_winloop.py')
    with open(script, 'w') as file:
        file.write(source.replace('3000', str(port)))

    # Windows has no INT of another process: Ctrl-Break of a group of processes of its own stops the server, as QUIT
    process = subprocess.Popen(
        [sys.executable, script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
    )
    try:
        status, body = get(port, time.monotonic() + 30)
        is_ok(status, 200, 'right status')
        is_ok(body, b'Your Pyjo is working!', 'right content')
    finally:
        process.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == 'win32' else signal.SIGINT)
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        output = process.stdout.read()
        process.stdout.close()
    is_ok(process.returncode, 0, 'stopped by Ctrl-Break')
    like_ok(output, rf'Web application available at http://127\.0\.0\.1:{port}', 'listening')

with subtest('asyncio_winloop.py'):
    result = subprocess.run(
        [sys.executable, os.path.join(EXAMPLES, 'asyncio_winloop.py')], capture_output=True, text=True, timeout=60
    )
    is_ok(
        result.stdout,
        'asyncio: HTTP/1.1 200 OK\nPyjo.UserAgent: 200 Your Pyjo is working!\nloop: winloop\n',
        'the streams of asyncio and the user agent of Pyjoyment on the loop of Winloop',
    )
    is_ok(result.stderr, '', 'nothing on the standard error')
    is_ok(result.returncode, 0, 'the server and the user agent closed at the end')

# As the workflow Build runs it with the wheel: its server listens on a port that the system picks, so it needs no free
# port of the tests
with subtest('loopback_winloop.py'):
    result = subprocess.run(
        [sys.executable, os.path.join(EXAMPLES, 'loopback_winloop.py')], capture_output=True, text=True, timeout=60
    )
    is_ok(
        result.stdout,
        'Pyjo_Reactor_Winloop winloop\n200 Your Pyjo is working!\n',
        'the response on the loop of Winloop',
    )
    is_ok(result.stderr, '', 'nothing on the standard error')
    is_ok(result.returncode, 0, 'the server and the user agent closed at the end')

done_testing()
