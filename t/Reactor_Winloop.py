import os


# The template of the test of the reactor, to be t/Reactor_Uvloop.py of Pyjo-Reactor-Uvloop, t/Pyjo/Reactor_Asyncio.py
# of Pyjoyment with subtests of its own, for the loop of Winloop. The reactor of the test is selected before Pyjo.IOLoop
# is loaded, as Pyjo.Reactor.detect() prefers Pyjo.Reactor.Asyncio
os.environ['PYJO_REACTOR'] = 'Pyjo.Reactor.Winloop'

import Pyjo.Reactor  # noqa: E402
import Pyjo.Reactor.Winloop  # noqa: E402

from Pyjo.Test import *  # noqa: E402


with subtest('Reactor detection'):
    is_ok(Pyjo.Reactor.object.detect(), 'Pyjo.Reactor.Winloop', 'right class')
    reactor = Pyjo.Reactor.Winloop.new()
    is_ok(type(reactor), Pyjo.Reactor.Winloop.object, 'right object')

done_testing()
