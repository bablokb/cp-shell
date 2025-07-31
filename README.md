cpshell
=======

Cpshell is a a port of the MicroPython rshell: <https://github.com/dhylands/rshell>.

It is a command-shell that allows you to create, copy and delete files on
UART-only CircuitPython devices.

If native USB is available, you should use the CIRCUITPY-drive since it
is much more performant. Likewise, if the web-workflow is up and running
it is faster. But there are still some use-cases where cpshell is the tool
of choice:

  - bootstrapping of `settings.toml` for the web-workflow
  - web-workflow not operational, e.g. because of a weak WLAN
  - wifi should not start automatically (e.g. for memory-reasons)
  - deactivated CIRCUITPY-drive in `boot.py`
  - read-only CIRCUITPY-drive

Major changes compared to rshell:

  - remove MicroPython specific code, e.g. for connecting using telnet
  - fixes necessary for CircuitPython
  - fixes for devices non CircuitPython devices
  - fail fast if a connection cannot be established
  - cpshell defaults to verbose-mode. Use `-q`/`--quiet` to supress
    informational messages
  - removed some features to simplify the codebase
    (e.g. **cpshell only supports a single connected device**)
  - refactor code (multiple modules instead of a gigantic
    `main.py` with more than 3K lines)
  - removal of dead code
  - no more `global` statements ;-)
  - better localization
  - remote files all start with a simple `:`, so the chance to shoot
    yourself into the foot with `rm -fr` or `rsync` is smaller

Besides these changes, there have been only cosmetic updates (the code
of rshell is old, but of high quality). This also implies that some of
the quirks of rshell and the rshell-commands still exist. One example
is that `rsync /dir` behaves like `rsync /dir/`. This might be changed
in a later update.


Builtin help
------------

Cpshell is a commandline tool with options (e.g. `--port`),
commands (e.g. `cp`) and arguments (e.g. the source-directory for the
`cp`-command). Some commands have their own options (the `cp`-command
for example has an `-r` option for recursive copy operations).

To print all available options for cpshell, all commands or help for a
specific command, run:


    $ cpshell -h
    $ cpshell help
    $ cpshell help rsync


Basic usage examples
--------------------

Note that in all examples, the leading '/' after the ':' can be omitted,
since the root-directory of the device is the default working directory.

Cpshell will automatically try to connect to a device on one of these
ports:

  - the value of the environment variable `CP_SHELL`
  - `/dev/ttyUSB0`
  - `/dev/ttyACM0`

You can override this with passing the port using the `-p`/`--port`
option on the commandline. As an alternative, pass
`--no-autoconnect`. This will take you to the shell (of cpshell). From
there, you can use various commands including `connect`.

Copy my version of `settings.toml` to the device:

    $ cpshell cp mysettings.toml :/settings.toml

Print `boot_out.txt`:

    $ cpshell cat :/boot_out.txt

Deploy source-tree (mirror-mode) from the local drive to the device:

    $ cpshell rsync -m src/ :/

List files on the device:

    $ cpshell ls -l :/
    $ cpshell ls -l :/lib

Run some code on the device. To prevent expansion by the os-shell
(e.g. bash), put the whole code in quotes. Within the code, use
`~` or `\;` as separators (a single semicolon is a separator for
cpshell-commands and must therefore be escaped).

A trailing `~` or `\;` will terminate the REPL after execution.

    $ cpshell repl 'import board~ print(board.board_id)~'

Enter the shell (first command), list all available commands and
request help for the `connect` command and exit again:

    $ cpshell
    cpshell> help
    cpshell> help connect
    cpshell> connect /dev/ttyACM0
    cpshell> exit
    $


Installation
------------

Run

    git clone https://github.com/bablokb/cp-shell
    cd cp-shell
    pip3 install .

If in doubt, create a python virtual environment first. Run the last command
as root to install globally (not recommended).


Troubleshooting
---------------

If you have problems or cpshell seems to hang, try running in
debug-mode (pass `-d`/`--debug` to cpshell).

If a connection to the REPL fails, it might be due to a slow
device. In this case pass e.g. `-W 4`/`--wait-repl 4` to cpshell. This
will give the device more time to boot CircuitPython.

To enter the raw REPL, cpshell will reset the device and check for the
"`soft reboot`" message from the REPL. The exact text of this message
depends on the locale (language) of the installed *CircuitPython
version*. Cpshell guesses the locale from the locale of the host which
might or might not be identical. You can pass the correct locale with
the option `-L` or `--locale`, e.g. `--locale de_DE`.  If this does
not work, check if your locale is available in `cpshell/cplocale.py`
and create a PR if not.

Cpshell is slow, since it uses the raw REPL to communicate with the
device.  Since the repl-buffer is not large, code and data needs to be
transferred in chunks with intermittent waits from the host to the
device. The default settings are conservative (chunk-size is 64 byte,
wait is 0.5s). Some devices allow much larger chunk-sizes. Use the
cpshell options `--chunk-size` and `--chunk-wait` to change the
defaults. Wrong values will cause a hang or timeout already by small
transfers.
