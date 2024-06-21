cp-shell
========

CP-shell is a command-shell for UART-only CircuitPython devices.
It is a port of the MicroPython rshell: <https://github.com/dhylands/rshell>.

Major changes:

  - remove MicroPython specific code, e.g. for connecting using telnet
  - fixes necessary for CircuitPython
  - removed some features to simplify the codebase (e.g. support only a single
    connected device)
  - refactor code (multiple modules instead of a gigantic `main.py` with more than 3K lines)
  - no more `global` statements ;-)
  - remote files all start with a simple `:`, so the chance to shoot yourself into the foot
    with `rm -fr` or `rsync` is smaller

Besides these changes, there have been only cosmetic changes (the code of rshell is of
very high quality). This also implies that some of the semantics of rshell-commands
(e.g. `rsync /dir` behaves like `rsync /dir/`) still exist. This might be changed in a
later update.
