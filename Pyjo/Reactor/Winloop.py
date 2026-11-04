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
the place of the one of :mod:`asyncio`, so that the servers of Pyjoyment, as
:mod:`Pyjo.Server.Daemon` and :mod:`Pyjo.Server.Prethread`, and the blocking
requests of its user agent run on Winloop on Windows. ``PYJO_REACTOR``
selects it for :mod:`Pyjo.IOLoop`::

    PYJO_REACTOR=Pyjo.Reactor.Winloop python myapp.py daemon

The reactor is not implemented yet.

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

import importlib.metadata

from typing import Any


__version__ = importlib.metadata.version('Pyjo-Reactor-Winloop')
"""The version of the distribution, of its metadata, which the workflow Automated version sets in pyproject.toml."""


class Pyjo_Reactor_Winloop(Pyjo.Reactor.Asyncio.object):
    """
    :mod:`Pyjo.Reactor.Winloop` inherits all methods from
    :mod:`Pyjo.Reactor.Asyncio`.
    """

    # The template of the distribution: the reactor on Winloop is to be written, so that nothing falls back to the loop
    # of asyncio in the meantime
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError('Pyjo.Reactor.Winloop is not implemented yet')


new = Pyjo_Reactor_Winloop.new
object = Pyjo_Reactor_Winloop
Winloop = Pyjo_Reactor_Winloop
