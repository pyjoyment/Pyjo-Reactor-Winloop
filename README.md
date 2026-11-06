[![Home](https://img.shields.io/badge/%F0%9F%8F%A0-Pyjoyment-02a7a0)](https://pyjoyment.dev/)
[![GitHub](https://img.shields.io/github/stars/pyjoyment/Pyjo-Reactor-Winloop?style=flat&label=GitHub%20%E2%AD%90&logo=github)](https://github.com/pyjoyment/Pyjo-Reactor-Winloop)
[![Documentation](https://img.shields.io/badge/docs-Read_the_Docs-blue?logo=readthedocs&logoColor=white)](https://pyjoyment.readthedocs.io/projects/pyjo-reactor-winloop/en/stable/)
[![License](https://img.shields.io/github/license/pyjoyment/Pyjo-Reactor-Winloop.svg)](https://github.com/pyjoyment/Pyjo-Reactor-Winloop/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/Pyjo-Reactor-Winloop?logo=pypi&logoColor=white)](https://pypi.org/project/Pyjo-Reactor-Winloop/)
[![Tests](https://github.com/pyjoyment/Pyjo-Reactor-Winloop/actions/workflows/tests.yaml/badge.svg?branch=main)](https://github.com/pyjoyment/Pyjo-Reactor-Winloop/actions/workflows/tests.yaml)
[![Trunk Check](https://github.com/pyjoyment/Pyjo-Reactor-Winloop/actions/workflows/trunk-check.yaml/badge.svg?branch=main)](https://github.com/pyjoyment/Pyjo-Reactor-Winloop/actions/workflows/trunk-check.yaml)

# Pyjo-Reactor-Winloop

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/pyjoyment/Pyjoyment/main/Pyjoyment/resources/public/pyjo/logo-white-4x.png">
    <img src="https://raw.githubusercontent.com/pyjoyment/Pyjoyment/main/Pyjoyment/resources/public/pyjo/logo-black-4x.png" alt="Pyjoyment" width="322">
  </picture>
</p>

Low level event reactor with [Winloop](https://github.com/Vizonex/Winloop)
support for [Pyjoyment](https://pyjoyment.dev/).

`Pyjo.Reactor.Winloop` is `Pyjo.Reactor.Asyncio` with an event loop of its
own of Winloop, the fork of uvloop for Windows, so that the servers of
Pyjoyment, `daemon` and `prethread`, and the blocking requests of its user
agent run on Winloop, with coroutines, tasks and the libraries of asyncio
along with them.

## Installation

From [PyPI](https://pypi.org/project/Pyjo-Reactor-Winloop/), with
[Pyjoyment](https://pypi.org/project/Pyjoyment/) and
[Winloop](https://pypi.org/project/winloop/), which it depends on, on Windows,
with CPython:

```sh
pip install Pyjo-Reactor-Winloop
```

or, in a project managed with [uv](https://docs.astral.sh/uv/):

```sh
uv add Pyjo-Reactor-Winloop
```

The development version is installed from the Git repository:

```sh
pip install git+https://github.com/pyjoyment/Pyjo-Reactor-Winloop
```

## Usage

Select the reactor with `PYJO_REACTOR` before `Pyjo.IOLoop` is loaded, in
PowerShell:

```powershell
$env:PYJO_REACTOR = 'Pyjo.Reactor.Winloop'
python myapp.py daemon
python myapp.py prethread
```

or in Git Bash:

```sh
PYJO_REACTOR=Pyjo.Reactor.Winloop python myapp.py daemon
```

## Examples

`examples/hello_world_winloop.py` runs `Pyjo.HelloWorld` on the server of
Pyjoyment on Winloop until Ctrl-C or Ctrl-Break, in a `with` block, which
closes the listen sockets of the server at its end:

```python
import os


# The reactor of Pyjoyment on Winloop, selected before Pyjo.IOLoop is loaded
os.environ['PYJO_REACTOR'] = 'Pyjo.Reactor.Winloop'

import Pyjo.HelloWorld  # noqa: E402
import Pyjo.Server.Daemon  # noqa: E402


# The server of Pyjoyment on Winloop, until Ctrl-C or Ctrl-Break, which closes its listen sockets at the end of the block
with Pyjo.Server.Daemon.new(app=Pyjo.HelloWorld.new(), listen=['http://*:3000']) as daemon:
    daemon.run()
```

```console
$ python examples/hello_world_winloop.py
Web application available at http://127.0.0.1:3000
```

```console
$ curl http://127.0.0.1:3000/
Your Pyjo is working!
```

`examples/asyncio_winloop.py` is a coroutine on the loop of Winloop, which
requests the server of Pyjoyment in the same loop with the streams of asyncio
and with the user agent of Pyjoyment, as the libraries of asyncio run along
with the reactor:

```python
import os


# The reactor of Pyjoyment on Winloop, selected before Pyjo.IOLoop is loaded
os.environ['PYJO_REACTOR'] = 'Pyjo.Reactor.Winloop'

import Pyjo.HelloWorld  # noqa: E402
import Pyjo.IOLoop  # noqa: E402
import Pyjo.Server.Daemon  # noqa: E402
import Pyjo.UserAgent  # noqa: E402

import asyncio  # noqa: E402

import winloop  # noqa: E402


# A coroutine on the loop of Winloop, with the streams of asyncio and the user agent of Pyjoyment, both requesting the
# server of Pyjoyment in the same loop
async def main(port):
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    writer.write(b'GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n')
    print(f'asyncio: {(await reader.readline()).decode().strip()}')
    writer.close()
    await writer.wait_closed()

    with Pyjo.UserAgent.new() as ua:
        tx = await ua.get_p(f'http://127.0.0.1:{port}/')
        print(f'Pyjo.UserAgent: {tx.res.code} {tx.res.text}')

    return 'winloop' if isinstance(asyncio.get_running_loop(), winloop.Loop) else 'asyncio'


# The server, on a port that the system picks, which closes its listen sockets at the end of the block
with Pyjo.Server.Daemon.new(app=Pyjo.HelloWorld.new(), listen=['http://127.0.0.1'], silent=True) as daemon:
    port = daemon.start().ports()[0]
    Pyjo.IOLoop.singleton.reactor.run_coroutine(
        main(port),
        lambda loop: (print(f'loop: {loop}'), Pyjo.IOLoop.stop()),
        lambda err: (print(f'error: {err}'), Pyjo.IOLoop.stop()),
    )
    Pyjo.IOLoop.start()
```

```console
$ python examples/asyncio_winloop.py
asyncio: HTTP/1.1 200 OK
Pyjo.UserAgent: 200 Your Pyjo is working!
loop: winloop
```

`examples/loopback_winloop.py` is a server of Pyjoyment and its user agent on
the loop of Winloop, a blocking request, which runs the event loop until the
response, and the class of the reactor and whether its loop is one of
Winloop, which Build checks with the wheel:

```python
import os


# The reactor of Pyjoyment on Winloop, selected before Pyjo.IOLoop is loaded
os.environ['PYJO_REACTOR'] = 'Pyjo.Reactor.Winloop'

import Pyjo.HelloWorld  # noqa: E402
import Pyjo.IOLoop  # noqa: E402
import Pyjo.Server.Daemon  # noqa: E402
import Pyjo.UserAgent  # noqa: E402

import winloop  # noqa: E402


# The server, on a port that the system picks, and the user agent, in the same event loop, which close their sockets at
# the end of the block
with (
    Pyjo.Server.Daemon.new(app=Pyjo.HelloWorld.new(), listen=['http://127.0.0.1'], silent=True) as daemon,
    Pyjo.UserAgent.new(ioloop=Pyjo.IOLoop.singleton) as ua,
):
    # A blocking request, which runs the event loop of the server on Winloop until the response
    tx = ua.get(f'http://127.0.0.1:{daemon.start().ports()[0]}/')
    reactor = Pyjo.IOLoop.singleton.reactor
    print(type(reactor).__name__, 'winloop' if isinstance(reactor.loop, winloop.Loop) else 'asyncio')
    print(tx.result.code, tx.result.text)
```

```console
$ python examples/loopback_winloop.py
Pyjo_Reactor_Winloop winloop
200 Your Pyjo is working!
```

## Documentation

The API of the module and the examples are on
[Read the Docs](https://pyjoyment.readthedocs.io/projects/pyjo-reactor-winloop/en/stable/).

## Status

A reactor of Pyjoyment in a distribution of its own, as
[Pyjo-Reactor-Uvloop](https://github.com/pyjoyment/Pyjo-Reactor-Uvloop),
which it follows on Windows.
