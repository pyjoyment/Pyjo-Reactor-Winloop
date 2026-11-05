# Agent Guide: Pyjo-Reactor-Winloop

## Overview

`Pyjo.Reactor.Winloop` is a reactor of Pyjoyment on the event loop of
Winloop, the fork of uvloop for Windows, in a distribution of its own, as
every reactor of Pyjoyment with a dependency is: Pyjoyment has no runtime
dependencies, and one reactor does not pull the dependencies of another. The
conventions are those of Pyjoyment: read its `AGENTS.md` in the checkout next
to this one, `../Pyjoyment/AGENTS.md`. The repository is made of the one of
Pyjo-Reactor-Uvloop, whose workflows and linters it shares, and whose
`AGENTS.md`, in `../Pyjo-Reactor-Uvloop`, says what the loop of uvloop needed.

## How it works

- It is `Pyjo.Reactor.Uvloop` for Winloop: a subclass of
  `Pyjo.Reactor.Asyncio`, as the loop of Winloop is a loop of asyncio, which
  overrides `_own_loop`, the loop that the reactor makes for itself: a
  subclass of `winloop.Loop` in the place of the `asyncio.SelectorEventLoop`
  that `Pyjo.Reactor.Asyncio` makes on Windows. The rest of what the reactor
  does with a loop of its own, which `_own_loop` repeats, the set of the loops
  that are closed at the exit of the interpreter, the finalizer that closes
  the loop with the reactor and its handler of `atexit`, are private members
  of `Pyjo.Reactor.Asyncio`, so a change of them in Pyjoyment breaks the
  reactor: the suite of Pyjoyment, which CI runs on the reactor, is what
  guards them.
- What the reactor is for is the servers of Pyjoyment, `daemon` and
  `prethread`, as Windows has no fork for `prefork`, and its blocking user
  agent, where no loop runs and the reactor makes one. libuv of Windows polls
  sockets only, with `uv_poll_init_socket` and the AFD of the I/O completion
  port, as `select` of Windows does, without its limit of 512 sockets; a pipe
  or a file cannot be watched, and `Pyjo.IOLoop.Stdio` is not available on
  Windows anyway.
- `_Loop` of `Pyjo.Reactor.Uvloop` works around five things of libuv and
  uvloop, which Winloop shares. They were checked in the sources of Winloop
  0.8.2 and of the libuv that it pins, 1.53, `src/win/core.c` and
  `src/win/poll.c`; two are taken, three are left out:
  - The hook of the finalizer of an async generator, taken: in the debug mode
    of asyncio, which CI runs with `PYTHONDEVMODE=1`, a handle of Winloop
    takes the stack where it is made, with `Sys_GetFrame` of its C, which is
    `PyThreadState_GetFrame`, the frame that `sys._getframe` of uvloop reads.
    The hook of Winloop, `_asyncgen_finalizer_hook`, of Cython, makes a handle
    with `call_soon_threadsafe` while CPython clears the frame of another
    async generator, as `head` of `Pyjo.Iterator` does, which crashed uvloop
    (MagicStack/uvloop#756). `_Loop` overrides the hook in Python, which the
    stack starts from then, as the hook of asyncio does, until a fix of it is
    released in Winloop.
  - The halt of the readers and the writers after `stop`, taken: `uv_run` of
    Windows processes the completions of its port, which are the callbacks of
    the readers and the writers, after its poll, and the next iteration runs
    the idle handle, where Winloop calls `uv_stop`, and polls once more, with
    no wait, before it ends. An event of the reactor that stops it, or ends
    `one_tick`, would be followed by the same events, as with uvloop on POSIX.
    `stop` of `_Loop` schedules a callback, which the idle handle runs before
    that poll, and which halts the readers and the writers until the end of
    the run. libuv submits the poll of a socket again after its callback, so a
    socket that is ready is ready in the next run still. A completion that is
    left over after the eight rounds of the processing of the iteration that
    stops runs before the idle handle, which is not halted.
  - The relay of the wakeup fd of the signals, left out: Winloop sets a socket
    of its own as the wakeup fd in `run_forever`, in the main thread, as
    uvloop does, but nothing of Pyjoyment on Windows waits for the wakeup fd
    of its own with the reactor while it runs. The worker of
    `Pyjo.Server.Prefork` that needed it does not exist on Windows; the
    manager of `Pyjo.Server.Prethread` waits for it with `select.select`,
    where no loop runs; its workers run the reactor in threads, where Winloop
    sets no wakeup fd; and the handler of `Pyjo.Server.Daemon` stops the loop
    itself, after Winloop, woken by its own socket, calls
    `PyErr_CheckSignals`. The relay of uvloop writes with `os.write` too, and
    the wakeup fd of Windows is a socket, which needs `send`.
  - The blocking mode of a handle, left out: `uv_poll_init_socket` sets a
    socket to the non-blocking mode, but the mode of a socket of Windows
    cannot be read, as `os.get_blocking` takes a descriptor of the C runtime
    and not a socket, and the terminal of `Pyjo.IOLoop.Stdio`, for which
    uvloop needed it, is not watched on Windows. The sockets of Pyjoyment are
    non-blocking. A `socket.socket` that is blocking, and that the reactor
    watches, raises `BlockingIOError` after it, where the loop of asyncio
    leaves it blocking; `sock.getblocking()` and `sock.setblocking(True)`
    after `add_reader` and `add_writer` would set it back, if a test shows
    the need.
  - The watch again after an error of a handle, left out: libuv of Windows
    reports the reset of a socket and the close of its peer as events of AFD,
    `AFD_POLL_ABORT` and `AFD_POLL_DISCONNECT`, which are readable, and keeps
    watching the socket, so its callbacks are called for as long as the
    error lasts, as with the loop of asyncio. It stops watching only on an
    error of the poll itself, as of a socket that is closed, and `select.poll`,
    with which uvloop checks `POLLERR` on Linux, does not exist on Windows.
- A socket that loops of the process watch, as the workers of
  `Pyjo.Server.Prethread` watch the listen sockets of the manager on Windows,
  the same sockets in every thread, is polled by one loop at a time. libuv of
  Windows submits every poll of AFD with `Exclusive = TRUE`, which ends the
  poll of the same socket of any other loop, also of a copy of the socket, as
  AFD is exclusive for the socket and not for its handle; that loop polls it
  again, and so on, in a busy loop of C with no event at all, which the
  documentation of libuv warns of: two idle loops took 70-80% of a processor,
  four took 240%, with or without the GIL, and starved the process, as
  `t/Pyjo/Server_Prethread.py` of Pyjoyment, and the tests next to it. `_Loop`
  keeps the readers and the writers of each socket, and a registry of the
  process, `_SOCKETS`, has the loops that watch it, the owner that libuv polls
  it for, and the loops that run and wait for it: the owner hands it over to
  the next one after each of its events, so the connections go to every worker
  in turn, and at the end of its run, and a loop that starts to run takes it
  from an owner that does not run. A loop changes the polls of libuv only in
  its thread, with `call_soon_threadsafe` when another loop hands a socket over
  to it. A socket that one loop watches goes to libuv as before, and the run
  of a loop looks at its sockets only while `_shared` counts sockets that more
  than one loop watches.
- `PYJO_ASYNCIO_SLOW_CALLBACK` sets the `slow_callback_duration` of a loop of
  its own, as for `Pyjo.Reactor.Asyncio`, which the loop of Winloop has too.
- `Pyjo.Reactor._finalize` defers the cleanup of a finalizer that runs below a
  frame of a reactor or of its event loop, since pyjoyment/Pyjoyment#534,
  which takes the file of the module of the class of the reactor,
  `Pyjo/Reactor/Winloop.py` with `_Loop`, wherever it is installed, and the
  modules of `event_loop_modules`. The reactor inherits
  `('asyncio', 'selectors')` and names no `winloop`: the loop of Winloop is
  compiled with Cython and makes no frames of Python, and the callbacks of
  the reactor run below `_Loop` or the methods of `Pyjo.Reactor.Asyncio`.
  The Python of the package is the code that `winloop.run` runs, its `run`
  and `wrapper`, below which is `asyncio/runners.py`, which `asyncio` covers
  already, and `_noop.noop`, which the loop calls to process the signals, and
  where a signal handler or the garbage collector may run: between the
  callbacks of libuv, and below `_Loop` for a loop of its own. A probe of
  `_finalize` over the suite of Pyjoyment on the reactor found no frame of
  Winloop below any of its calls (#2).
- Winloop has wheels for CPython on Windows only, with the free-threaded
  build, not for PyPy, so the matrix of Tests is CPython 3.12 to 3.15 and
  3.15t on `windows-2025`.

## Development

The distribution depends on the release of Pyjoyment on PyPI, with the lowest
version that has what it uses, which `uv.lock` pins. A change of Pyjoyment that
is not released yet would be its Git repository in `[tool.uv.sources]` of
`pyproject.toml`, until its release, and not a path to the checkout next to
this one: uv applies the sources of a dependency of Git, so whoever installs
the reactor from Git would get a subdirectory of this repository that does not
exist. That is the Pyjoyment of `main` now, for its tests that recognize a
subclass of `Pyjo.Reactor.Asyncio`, pyjoyment/Pyjoyment#510, and for the
finalizers deferred below the frames of the reactor, pyjoyment/Pyjoyment#534:
before a release
of the reactor, the source goes and the lowest version of `dependencies`
becomes the release of Pyjoyment that has it, as a wheel carries no sources of
uv and would install Pyjoyment 0.2.0.
The tests lay the checkout next to this one over it with `--with-editable`,
so that they test what is there:
Winloop is installed on Windows only, `sys_platform == 'win32'` of
`dependencies`, as it has wheels for Windows only, so the tests run on Windows,
and CI runs them on `windows-2025`; on Linux and macOS, where Trunk and Read
the Docs run, the environment has no Winloop.


```sh
mise exec -- uv sync
mise exec -- uv run --with-editable ../Pyjoyment python -m Pyjo.Prove -l -r t
```

Perl's `prove` runs them too, with `.proverc`, under `uv run`, whose `python`
is the one of the environment, where Pyjoyment and the reactor are installed,
so that it needs no `PYTHONPATH`, unlike in Pyjoyment:

```sh
mise exec -- uv run --with-editable ../Pyjoyment prove -r t
```

The tests of Pyjoyment run on this reactor as well, with `PYJO_REACTOR`:

```sh
cd ../Pyjoyment
PYJO_REACTOR=Pyjo.Reactor.Winloop mise exec -- uv run --project ../Pyjo-Reactor-Winloop --with-editable . \
  python -m Pyjo.Prove -l -j 4 -r t
```

The workflow Tests runs the tests of the reactor against the release of
`uv.lock`, without `--with-editable`, so that a pull request tests what an
installation gets, and the suite of Pyjoyment of the tag of that release on
the reactor, or of its commit when `uv.lock` has it from Git. A dispatch
with `pyjoyment-ref`, a branch, a tag or a commit of Pyjoyment, installs
its Pyjoyment of Git over it with `uv run --with`, not editable, as an
installation from Git gets it, and runs the suite of its checkout, so that
what the next release of Pyjoyment breaks is known before the release. It
ends with the job `Tests`, the one check of it that the ruleset of `main`
requires, as in Pyjoyment: it fails when a job of the matrix failed or was
cancelled, so a new version of Python needs no change of the ruleset.

Trunk checks the files with the linters of Pyjoyment, from `.trunk/trunk.yaml`:

```sh
trunk check --all
```

actionlint is the one of the maintained fork kjanat/actionlint, whose releases
continue those of rhysd/actionlint after 1.7.12, as in Pyjoyment: `downloads`
in `.trunk/trunk.yaml` replaces the URLs of the plugin with those of the fork,
whose files have the same names.

Biome formats and lints JSON, Markdown and YAML, with `biome.jsonc`, in the
place of prettier, markdownlint and yamlfmt, as in Pyjoyment, and yamllint
checks what Biome does not, as the duplicated keys. The version of Biome is
the pinned one of `.trunk/trunk.yaml`, where `!` keeps it from
`trunk upgrade`, and which Renovate bumps: the repository has no
`package.json` of its own. Renovate cannot run `biome migrate`, so the
workflow Biome Migrate runs it with `npx --yes @biomejs/biome@<version>` of
that version, migrates `biome.jsonc` on the branch of Renovate and commits it
with the token of the workflow, as the author that `gitIgnoredAuthors` of
`.renovaterc.json` names, so that Renovate keeps updating the branch, and
starts the checks of the commit with `workflow_dispatch`; anywhere else, a
`biome.jsonc` that this Biome would migrate fails the check. The definition of
Biome in `.trunk/trunk.yaml` is the one of Pyjoyment, which explains why it is
not the one of the plugin of Trunk.

Its pyright needs the environment of `uv sync`, `.venv`, which `tool.pyright` of
`pyproject.toml` names, as the reactor imports Pyjoyment, while Pyjoyment has
no dependencies to find; Trunk Check of CI runs `uv sync` first. Winloop is
not in that environment on Linux and macOS, so pyright takes the stub of
`typings/winloop`, the default `stubPath`, which has what the module uses of
Winloop, with the methods of asyncio that typeshed has abstract in
`asyncio.AbstractEventLoop` and `winloop.Loop` implements; the stub is taken on
Windows too, where it hides the types of Winloop itself. The import of Winloop
ignores `reportMissingModuleSource`, which pyright reports where only the stub
is found.
The examples and the tests, and `docs/conf.py`, are not checked by pyright: for them it takes the
regular package `Pyjo` of Pyjoyment, which hides `Pyjo.Reactor.Winloop` of the
checkout.

The documentation is one page, `docs/index.rst`: the docstrings of the
module, which autodoc imports, with a mock of Winloop, `autodoc_mock_imports`
of `docs/conf.py`, as Read the Docs and the workflow Docs build on Linux, and the examples from `examples/`, included,
never copied, as in Pyjoyment. Read the Docs installs it with `uv sync` of `uv.lock` and the
group `docs`, not with pip and a `docs/requirements.txt` as Pyjoyment does,
so that it builds with the versions of the lock, as the workflow Docs does.
The links to the modules of Pyjoyment come from intersphinx, to its stable
version from the stable one, and to latest from the others. The examples are
a rubric, not a section: they follow the docstring of the module, whose
sections are its own, so that a section would be a second title of the page.
The workflow Docs builds it with `-W`, as Read the Docs does, with the
Pyjoyment of `uv.lock`:

```sh
mise exec -- uv run --group docs --with-editable ../Pyjoyment sphinx-build -W --keep-going -b html docs docs/_build/html
```

`t/Reactor_Winloop.py` is `t/Reactor_Uvloop.py` of Pyjo-Reactor-Uvloop,
`t/Pyjo/Reactor_Asyncio.py` of Pyjoyment with subtests of its own for the
loop of Winloop: a loop of its own, a given loop, a loop that is running, of
asyncio, a `SelectorEventLoop`, and of Winloop, a coroutine,
`PYJO_ASYNCIO_SLOW_CALLBACK`, a signal while the loop waits, the finalizer of
an async generator in the debug mode, a stop in a callback of I/O, the
writer of a socket whose peer has closed it and a socket that reactors in
threads watch. The subtests of Uvloop for the
fork, the wakeup fd of a program and the blocking mode of a pipe are left out,
as they do not apply on Windows.
`t/examples.py` stops the server of `examples/hello_world_winloop.py` with
Ctrl-Break, `CTRL_BREAK_EVENT` to a group of processes of its own, as
`t/lib/ServerProcess.py` of Pyjoyment does, as Windows cannot send INT to
another process.
`t/docs/Reactor_Winloop.py` runs the synopsis of the module, in both forms, as
`t/docs` of Pyjoyment does.

## Releases

The releases are those of Pyjoyment, with its workflows: a release is a tag of
the version of `pyproject.toml`, without a `v`, as `0.2.0`, which Automated
version sets with `uv version`, the components of its `--bump` from a list, as
`patch dev` or `minor rc`, or the version of `manual`, in the pull request of
the branch `automated/version`. After a release, a pre-release goes with the
release that it comes before, as PEP 440 orders `0.2.0.dev1` before `0.2.0`,
so `dev` alone after `0.2.0` fails. Automated tag tags the merge commit of
that pull request when it is merged, or with a comment `/tag` of a maintainer
on it, and starts Release on the tag. A development version, as `0.2.1.dev1`,
is not tagged. The version is static in `pyproject.toml`, as `uv version`
cannot set a dynamic one, and `__version__` of the module reads it from the
metadata of the distribution.

Release builds the sdist and the wheel, attests their build provenance with
`actions/attest`, and makes a draft of the GitHub release with them, whose
notes are rewritten before it is published, and an SBOM in SPDX, attested
with them. The module bundles nothing, unlike the package of Pyjoyment, whose
SBOM lists the JavaScript libraries of its package, so the SBOM is what an
installation of the wheel gets: the distribution and its dependencies, as
Pyjoyment and Winloop, at the versions of `uv.lock`, installed in a virtual
environment of their own, which Syft scans. Syft on `uv.lock` itself would
take its dependency groups too, as Sphinx, which an installation does not get.
The sdist does not carry the SBOM, as the one of Pyjoyment does, as it is made
of the wheel, which is built after the sdist.

The workflow PyPI, run manually, publishes the files of the latest published
release, or of the release of the tag of its input, on PyPI once their
attestations of Release verify, in the environment `publishing`, which waits
for an approval and takes `main` and tags only. The trusted publisher of PyPI
names `pypi.yaml` and that environment.

```sh
gh attestation verify pyjo_reactor_winloop-0.2.0.tar.gz -R pyjoyment/Pyjo-Reactor-Winloop
```
