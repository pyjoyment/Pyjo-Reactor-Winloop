[![Home](https://img.shields.io/badge/%F0%9F%8F%A0-Pyjoyment-02a7a0)](https://github.com/pyjoyment/Pyjoyment)
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
support for [Pyjoyment](https://github.com/pyjoyment/Pyjoyment).

`Pyjo.Reactor.Winloop` is `Pyjo.Reactor.Asyncio` with an event loop of its
own of Winloop, the fork of uvloop for Windows, so that the servers of
Pyjoyment, `daemon` and `prethread`, and the blocking requests of its user
agent run on Winloop, with coroutines, tasks and the libraries of asyncio
along with them.

The reactor is not implemented yet: this is the template of the distribution.

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

Select the reactor with `PYJO_REACTOR` before `Pyjo.IOLoop` is loaded:

```sh
PYJO_REACTOR=Pyjo.Reactor.Winloop python myapp.py daemon
PYJO_REACTOR=Pyjo.Reactor.Winloop python myapp.py prethread
```

## Examples

`examples/hello_world_winloop.py` runs `Pyjo.HelloWorld` on the server of
Pyjoyment on Winloop until the signal `INT` or `TERM`, in a `with` block,
which closes the listen sockets of the server at its end:

```python
import os


# The reactor of Pyjoyment on Winloop, selected before Pyjo.IOLoop is loaded
os.environ['PYJO_REACTOR'] = 'Pyjo.Reactor.Winloop'

import Pyjo.HelloWorld  # noqa: E402
import Pyjo.Server.Daemon  # noqa: E402


# The server of Pyjoyment on Winloop, until the signal INT or TERM, which closes its listen sockets at the end of the block
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
