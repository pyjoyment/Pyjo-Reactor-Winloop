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
sets one of its own while it runs, in the main thread. A timer of a loop of
its own, as :func:`asyncio.sleep`, is never due before its time, as with the
loop of :mod:`asyncio`, although libuv counts it in whole milliseconds, so it
may be up to two milliseconds late.

Reactors in threads of a process that watch the same socket, as the workers
of :mod:`Pyjo.Server.Prethread` watch the listen sockets of the manager, take
turns: libuv of Windows cannot poll a socket for more than one loop at a time,
so the loop of one of them watches it, and hands it over to the next one after
each of its events, and when it stops running.

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
import collections
import importlib.metadata
import math
import os
import threading
import weakref

from collections.abc import Callable, Sequence
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


# A socket that loops of Winloop of the process watch, as the workers of Pyjo.Server.Prethread watch the listen sockets
# of the manager on Windows: libuv of Windows polls a socket with a request of AFD that is exclusive, which ends the
# request of any other loop for the same socket, also of a copy of it, and that loop polls it again, which ends the
# request of the first one, and so on, in a busy loop of C, with no event at all. One loop polls it at a time, its owner,
# and the others that run wait for it in turn: the owner hands it over to the next one after each of its events, so that
# the connections of a listen socket go to every loop, and when it stops running. A loop that does not run takes it from
# an owner that does not run either, once it runs
class _Socket:
    __slots__ = ('loops', 'owner', 'waiting')

    def __init__(self) -> None:
        self.loops: set[_Loop] = set()
        self.owner: _Loop | None = None
        self.waiting: collections.deque[_Loop] = collections.deque()


# The sockets by their numbers, which the lock guards, and how many of them more than one loop watches
_LOCK = threading.Lock()
_SOCKETS: dict[int, _Socket] = {}
_shared = 0


class _Loop(winloop.Loop):
    _halt: asyncio.Handle | None = None
    _halted = False
    _active = False

    def __init__(self) -> None:
        super().__init__()
        # The handle, the reader and the writer of each socket that the loop watches, and the handles of the ones that
        # libuv polls for it, which only the thread of the loop changes
        self._watched: dict[int, list[Any]] = {}
        self._polled: dict[int, Any] = {}

    # After stop, Winloop ends the iteration of libuv, and the iteration that a callback of I/O stops goes on to the poll
    # of the next one, where libuv of Windows takes the completions of its I/O completion port and calls the readers and
    # the writers that are ready again, as on POSIX, where the loop of asyncio ends with the callbacks of its select. A
    # callback that stop schedules runs before that poll, in the idle handle of Winloop, and halts the readers and the
    # writers until the end of the run; the poll of a socket is submitted again after its callback, so the socket is
    # ready in the next run still. A stop in a ready callback does not halt the poll of its own iteration, as the loop of
    # asyncio runs the callbacks of its select along with it, which would starve the I/O of one_tick otherwise
    def run_forever(self) -> None:
        if self.is_running():
            return super().run_forever()
        self._halted = False
        self._active = True
        if _shared:
            self._claim()
        try:
            return super().run_forever()
        finally:
            self._halted = False
            if (halt := self._halt) is not None:
                self._halt = None
                halt.cancel()
            self._active = False
            if _shared:
                self._yield()

    def stop(self) -> None:
        if self._halt is None and self.is_running():
            self._halt = self.call_soon(self._halting)
        super().stop()

    def _halting(self) -> None:
        self._halt = None
        self._halted = True

    # libuv counts a timer in whole milliseconds from its clock, which it rounds down, and Winloop rounds the delay, so
    # that a timer, as asyncio.sleep, is due up to a millisecond before its time by time.monotonic, where the loop of
    # asyncio is never early; the delay is rounded up, with the millisecond that the clock loses, as Pyjo.Reactor.Uvloop
    # does (MagicStack/uvloop#755). call_at of Winloop calls it too
    def call_later(
        self, delay: float, callback: Callable[..., Any], *args: Any, context: Any = None
    ) -> asyncio.TimerHandle:
        if 0 < delay < math.inf:
            delay = (math.ceil(delay * 1000) + 1) / 1000
        return super().call_later(delay, callback, *args, context=context)

    def add_reader(self, fd: Any, callback: Callable[..., Any], *args: Any) -> None:
        self._watch(fd, 1, (callback, args))

    def add_writer(self, fd: Any, callback: Callable[..., Any], *args: Any) -> None:
        self._watch(fd, 2, (callback, args))

    def remove_reader(self, fd: Any) -> bool:
        return self._unwatch(fd, 1)

    def remove_writer(self, fd: Any) -> bool:
        return self._unwatch(fd, 2)

    def close(self) -> None:
        super().close()
        with _LOCK:
            handovers = [self._leave(key) for key in self._watched]
            self._watched.clear()
        self._polled.clear()
        _Loop._hand_over(handovers)

    def _ready(self, key: int, callback: Callable[..., Any], *args: Any) -> None:
        if self._halted:
            return
        try:
            callback(*args)
        finally:
            # The next loop that waits for the socket takes it, and this one waits for it again
            if _shared and (sock := _SOCKETS.get(key)) is not None and sock.waiting and sock.owner is self:
                with _LOCK:
                    loop = _Loop._next(sock) if sock.owner is self and key in self._watched else None
                    if loop is not None:
                        sock.owner = loop
                        sock.waiting.append(self)
                if loop is not None:
                    self._sync(key)
                    _Loop._hand_over([(loop, key)])

    def _watch(self, fd: Any, index: int, cb: tuple[Callable[..., Any], tuple[Any, ...]]) -> None:
        global _shared
        key = _number(fd)
        with _LOCK:
            if (watched := self._watched.get(key)) is None:
                watched = self._watched[key] = [fd, None, None]
                if (sock := _SOCKETS.get(key)) is None:
                    sock = _SOCKETS[key] = _Socket()
                sock.loops.add(self)
                if len(sock.loops) == 2:
                    _shared += 1
            else:
                sock = _SOCKETS[key]
            watched[index] = cb
            self._contend(sock)
        self._sync(key, index)

    def _unwatch(self, fd: Any, index: int) -> bool:
        key = _number(fd)
        handover = None
        with _LOCK:
            if (watched := self._watched.get(key)) is None or watched[index] is None:
                return False
            watched[index] = None
            if watched[1] is None and watched[2] is None:
                del self._watched[key]
                handover = self._leave(key)
        self._sync(key, index)
        _Loop._hand_over([handover])
        return True

    # The loop owns the socket when nobody does, or when it runs and the owner does not, or else waits for it in turn
    # while it runs; with the lock
    def _contend(self, sock: _Socket) -> None:
        owner = sock.owner
        if owner is None or (self._active and owner is not self and not owner._active):
            sock.owner = self
        elif owner is not self and self._active and self not in sock.waiting:
            sock.waiting.append(self)

    # The loop stops watching the socket, which goes to the next loop that waits for it, or else to one that does not
    # run, which polls it once it runs; with the lock
    def _leave(self, key: int) -> 'tuple[_Loop, int] | None':
        global _shared
        sock = _SOCKETS[key]
        sock.loops.discard(self)
        if len(sock.loops) == 1:
            _shared -= 1
        if self in sock.waiting:
            sock.waiting.remove(self)
        if not sock.loops:
            del _SOCKETS[key]
            return None
        if sock.owner is not self:
            return None
        sock.owner = _Loop._next(sock) or next(iter(sock.loops))
        return sock.owner, key

    # At the start of a run, the loop takes the sockets of owners that do not run, waits for the others, and stops
    # polling the ones that another loop took while it did not run
    def _claim(self) -> None:
        with _LOCK:
            for key in self._watched:
                self._contend(_SOCKETS[key])
            keys = [key for key in self._watched if (_SOCKETS[key].owner is self) != (key in self._polled)]
        for key in keys:
            self._sync(key)

    # At the end of a run, the sockets that other loops wait for go to them
    def _yield(self) -> None:
        handovers: list[tuple[_Loop, int]] = []
        with _LOCK:
            for key in self._watched:
                sock = _SOCKETS[key]
                if self in sock.waiting:
                    sock.waiting.remove(self)
                if sock.owner is self and (loop := _Loop._next(sock)) is not None:
                    sock.owner = loop
                    handovers.append((loop, key))
        for _, key in handovers:
            self._sync(key)
        _Loop._hand_over(handovers)

    # libuv polls the socket for the loop as long as it owns it, with its reader and its writer, or only the one that
    # changed of a socket that it polls already; in the thread of the loop
    def _sync(self, key: int, index: int = 0) -> None:
        with _LOCK:
            sock = _SOCKETS.get(key)
            watched = self._watched.get(key) if sock is not None and sock.owner is self else None
            watched = list(watched) if watched is not None else None
        if self.is_closed():
            return
        if watched is not None:
            fd = watched[0]
            if key not in self._polled:
                index = 0
            self._polled[key] = fd
            if index != 2:
                if (reader := watched[1]) is not None:
                    super().add_reader(fd, self._ready, key, reader[0], *reader[1])
                else:
                    super().remove_reader(fd)
            if index != 1:
                if (writer := watched[2]) is not None:
                    super().add_writer(fd, self._ready, key, writer[0], *writer[1])
                else:
                    super().remove_writer(fd)
        elif (fd := self._polled.pop(key, None)) is not None:
            super().remove_reader(fd)
            super().remove_writer(fd)

    # The next loop that runs and waits for the socket; with the lock
    @staticmethod
    def _next(sock: _Socket) -> '_Loop | None':
        while sock.waiting:
            loop = sock.waiting.popleft()
            if loop._active and loop in sock.loops:
                return loop
        return None

    # A loop that takes a socket polls it in its thread; a loop that is closed has left it to the next one already
    @staticmethod
    def _hand_over(handovers: 'Sequence[tuple[_Loop, int] | None]') -> None:
        for handover in handovers:
            if handover is not None:
                loop, key = handover
                try:
                    loop.call_soon_threadsafe(loop._sync, key)
                except RuntimeError:
                    pass

    # The finalizer of an async generator, which a dealloc calls while CPython clears a frame, in Python, as the one of
    # asyncio: the handle of Winloop takes the stack in the debug mode with the current frame of the thread, which
    # crashes on the frame that is cleared when the hook of Cython is the top of the stack, as in uvloop
    # (MagicStack/uvloop#756)
    def _asyncgen_finalizer_hook(self, agen: Any) -> None:
        super()._asyncgen_finalizer_hook(agen)


def _number(fd: Any) -> int:
    return fd if isinstance(fd, int) else int(fd.fileno())


# The threshold of a slow callback of PYJO_ASYNCIO_SLOW_CALLBACK, as for a loop of its own of Pyjo.Reactor.Asyncio
def _new_event_loop() -> asyncio.AbstractEventLoop:
    loop = _Loop()
    if duration := os.environ.get('PYJO_ASYNCIO_SLOW_CALLBACK'):
        loop.slow_callback_duration = float(duration)
    return loop


new = Pyjo_Reactor_Winloop.new
object = Pyjo_Reactor_Winloop
Winloop = Pyjo_Reactor_Winloop
