.. automodule:: Pyjo.Reactor.Winloop
    :members:

.. The examples follow the API, after the docstring of the module, which ends with its classes: a section here would
   be a second title of the page, as the sections of the docstring are its own.

.. rubric:: Examples
    :heading-level: 2
    :name: examples

``examples/hello_world_winloop.py`` runs ``Pyjo.HelloWorld`` on the server of
Pyjoyment on Winloop until Ctrl-C or Ctrl-Break, in a ``with`` block,
which closes the listen sockets of the server at its end:

    .. include:: ../examples/hello_world_winloop.py
       :code: python

.. code-block:: console

    $ python examples/hello_world_winloop.py
    Web application available at http://127.0.0.1:3000

.. code-block:: console

    $ curl http://127.0.0.1:3000/
    Your Pyjo is working!

``examples/asyncio_winloop.py`` is a coroutine on the loop of Winloop, which
requests the server of Pyjoyment in the same loop with the streams of
:mod:`asyncio` and with the user agent of Pyjoyment, as the libraries of
:mod:`asyncio` run along with the reactor:

    .. include:: ../examples/asyncio_winloop.py
       :code: python

.. code-block:: console

    $ python examples/asyncio_winloop.py
    asyncio: HTTP/1.1 200 OK
    Pyjo.UserAgent: 200 Your Pyjo is working!
    loop: winloop

``examples/loopback_winloop.py`` is a server of Pyjoyment and its user agent on
the loop of Winloop, a blocking request, which runs the event loop until the
response, and the class of the reactor and whether its loop is one of
Winloop:

    .. include:: ../examples/loopback_winloop.py
       :code: python

.. code-block:: console

    $ python examples/loopback_winloop.py
    Pyjo_Reactor_Winloop winloop
    200 Your Pyjo is working!
