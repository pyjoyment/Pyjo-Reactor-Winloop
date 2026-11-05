"""
Pyjo.Reactor.Winloop - Low-level event reactor on Winloop
=========================================================
::

    from Pyjo.Reactor.Winloop import Winloop

    # Watch if handle becomes readable or writable
    reactor = Winloop()
    reactor.io(first, lambda reactor, writable: print(
        'First handle is writable' if writable else 'First handle is readable'
    ))

    # Or import the module, as in Google Python Style Guide

    import Pyjo.Reactor.Winloop

    # Watch if handle becomes readable or writable
    reactor = Pyjo.Reactor.Winloop.new()
    reactor.io(first, lambda reactor, writable: print(
        'First handle is writable' if writable else 'First handle is readable'
    ))

    # Change to watching only if handle becomes writable
    reactor.watch(first, False, True)

    # Watch a file descriptor if it becomes readable
    reactor.io(fd, lambda reactor, writable: print(
        'Second handle is writable' if writable else 'Second handle is readable'
    )).watch(fd, True, False)

    # Add a timer
    def timeout(reactor):
        reactor.remove(first)
        reactor.remove(fd)
        print('Timeout!')

    reactor.timer(15, timeout)

    # Start reactor if necessary
    if not reactor.is_running:
        reactor.start()

:mod:`Pyjo.Reactor.Winloop` is a low-level event reactor based on
`Winloop <https://github.com/Vizonex/Winloop>`_, the fork of uvloop for
Windows, the implementation of the event loop of :mod:`asyncio` on libuv. It
is :mod:`Pyjo.Reactor.Asyncio` with an event loop of its own of Winloop, in
the place of the :class:`asyncio.SelectorEventLoop` that
:mod:`Pyjo.Reactor.Asyncio` makes on Windows, so that the servers of
Pyjoyment, as :mod:`Pyjo.Server.Daemon` and :mod:`Pyjo.Server.Prethread`,
and the blocking requests of its user agent run on Winloop. ``PYJO_REACTOR``
selects it for :mod:`Pyjo.IOLoop`, in PowerShell::

    $env:PYJO_REACTOR = 'Pyjo.Reactor.Winloop'
    python myapp.py daemon

The loop of Winloop is a loop of :mod:`asyncio`, so coroutines, tasks and the
libraries of :mod:`asyncio` run along with the reactor, as with
:mod:`Pyjo.Reactor.Asyncio`. It watches sockets, as the
:class:`asyncio.SelectorEventLoop` of Windows does, not pipes or files, but
with the I/O completion ports of libuv, without the limit of 512 sockets of
:func:`select.select`. A reactor uses the event loop it is given, or else the
loop that is running, as inside :func:`asyncio.run`, which has to be able to
watch handles, as a loop of Winloop or an :class:`asyncio.SelectorEventLoop`
is, and only a loop of its own is one of Winloop. An ASGI server that runs a
loop of Winloop itself, as with ``loop_factory=winloop.new_event_loop``, is
taken by :mod:`Pyjo.Reactor.Asyncio` already, so it needs no reactor of
Winloop.

A signal handler of Python runs while a loop of its own waits, as on the
Ctrl-C or Ctrl-Break that stops a server, but the wakeup fd that a program
sets with :func:`signal.set_wakeup_fd` is not written to then, as Winloop
sets one of its own while it runs, in the main thread.

Winloop runs on Windows, and on CPython, not on PyPy. The
``PYJO_ASYNCIO_SLOW_CALLBACK`` environment variable sets the
``slow_callback_duration`` of a loop of its own in seconds, as for
:mod:`Pyjo.Reactor.Asyncio`.

Events
------

:mod:`Pyjo.Reactor.Winloop` inherits all events from :mod:`Pyjo.Reactor.Asyncio`.

See also
--------

:mod:`Pyjo.Reactor.Asyncio`, :mod:`Pyjoyment`, https://github.com/pyjoyment/Pyjoyment.

Classes
-------
"""

import Pyjo.Reactor.Asyncio

import asyncio
import importlib.metadata
import os
import weakref

from collections.abc import Callable
from typing import Any

# Winloop is installed on Windows only, and pyright of Linux and macOS takes the stub of typings/winloop
import winloop  # pyright: ignore[reportMissingModuleSource]


__version__ = importlib.metadata.version('Pyjo-Reactor-Winloop')
"""The version of the distribution, of its metadata, which the workflow Automated version sets in pyproject.toml."""


class Pyjo_Reactor_Winloop(Pyjo.Reactor.Asyncio.object):
    """
    :mod:`Pyjo.Reactor.Winloop` inherits all methods from
    :mod:`Pyjo.Reactor.Asyncio`.
    """

    # A loop of its own of Winloop, in the place of the one of asyncio; the rest is what Pyjo.Reactor.Asyncio does with a
    # loop of its own, which is closed with the reactor, and at the exit of the interpreter after its tasks
    def _own_loop(self) -> asyncio.AbstractEventLoop:
        loop = self._own = _new_event_loop()
        Pyjo.Reactor.Asyncio._OWN.add(loop)  # pyright: ignore[reportPrivateUsage]
        self._finalizer = weakref.finalize(self, Pyjo.Reactor.Asyncio._close, loop)  # pyright: ignore[reportPrivateUsage]
        Pyjo.Reactor.Asyncio._register()  # pyright: ignore[reportPrivateUsage]
        return loop


class _Loop(winloop.Loop):
    _halt: asyncio.Handle | None = None
    _halted = False

    # After stop, Winloop ends the iteration of libuv, and the iteration that a callback of I/O stops goes on to the poll
    # of the next one, where libuv of Windows takes the completions of its I/O completion port and calls the readers and
    # the writers that are ready again, as on POSIX, where the loop of asyncio ends with the callbacks of its select. A
    # callback that stop schedules runs before that poll, in the idle handle of Winloop, and halts the readers and the
    # writers until the end of the run; the poll of a socket is submitted again after its callback, so the socket is
    # ready in the next run still. A stop in a ready callback does not halt the poll of its own iteration, as the loop of
    # asyncio runs the callbacks of its select along with it, which would starve the I/O of one_tick otherwise
    def run_forever(self) -> None:
        self._halted = False
        try:
            return super().run_forever()
        finally:
            self._halted = False
            if (halt := self._halt) is not None:
                self._halt = None
                halt.cancel()

    def stop(self) -> None:
        if self._halt is None and self.is_running():
            self._halt = self.call_soon(self._halting)
        super().stop()

    def _halting(self) -> None:
        self._halt = None
        self._halted = True

    def add_reader(self, fd: Any, callback: Callable[..., Any], *args: Any) -> None:
        super().add_reader(fd, self._ready, callback, *args)

    def add_writer(self, fd: Any, callback: Callable[..., Any], *args: Any) -> None:
        super().add_writer(fd, self._ready, callback, *args)

    def _ready(self, callback: Callable[..., Any], *args: Any) -> None:
        if not self._halted:
            callback(*args)

    # The finalizer of an async generator, which a dealloc calls while CPython clears a frame, in Python, as the one of
    # asyncio: the handle of Winloop takes the stack in the debug mode with the current frame of the thread, which
    # crashes on the frame that is cleared when the hook of Cython is the top of the stack, as in uvloop
    # (MagicStack/uvloop#756)
    def _asyncgen_finalizer_hook(self, agen: Any) -> None:
        super()._asyncgen_finalizer_hook(agen)


# The threshold of a slow callback of PYJO_ASYNCIO_SLOW_CALLBACK, as for a loop of its own of Pyjo.Reactor.Asyncio
def _new_event_loop() -> asyncio.AbstractEventLoop:
    loop = _Loop()
    if duration := os.environ.get('PYJO_ASYNCIO_SLOW_CALLBACK'):
        loop.slow_callback_duration = float(duration)
    return loop


new = Pyjo_Reactor_Winloop.new
object = Pyjo_Reactor_Winloop
Winloop = Pyjo_Reactor_Winloop
