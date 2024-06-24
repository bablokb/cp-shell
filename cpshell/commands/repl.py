# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'repl' command.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

import time
import threading

from cpshell.getch import getch
from cpshell import utils
from cpshell import device

from .command import Command

QUIT_REPL_CHAR = 'X'
QUIT_REPL_BYTE = bytes((ord(QUIT_REPL_CHAR) - ord('@'),))  # Control-X

# --- helper-class   ----------------------------------------------------------

class AutoBool(object):
  """A simple class which allows a boolean to be set to False in conjunction
    with a with: statement.
  """

  def __init__(self):
    self.value = False

  def __enter__(self):
    self.value = True

  def __exit__(self, type, value, traceback):
    self.value = False

  def __call__(self):
    return self.value

# --- command class for repl   -----------------------------------------------

class Repl(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"repl")

  # --- background thread piping from serial to stdout   ---------------------

  def _repl_serial_to_stdout(self, dev):
    """Runs as a thread which has a sole purpose of reading bytes from
      the serial port and writing them to stdout. Used by do_repl.
    """
    with self._serial_reader_running:
      try:
        save_timeout = dev.timeout
        # Set a timeout so that the read returns periodically with no data
        # and allows us to check whether the main thread wants us to quit.
        dev.timeout = 1
        while not self._quit_serial_reader:
          try:
            char = dev.read(1)
          except serial.serialutil.SerialException:
            # This happens if the board reboots, or a USB port
            # goes away.
            return
          except TypeError:
            # This is a bug in serialposix.py starting with python 3.3
            # which causes a TypeError during the handling of the
            # select.error. So we treat this the same as
            # serial.serialutil.SerialException:
            return
          if not char:
            # This means that the read timed out. We'll check the quit
            # flag and return if needed
            if self._quit_when_no_output:
              break
            continue
          self.shell.stdout.write(char)
          self.shell.stdout.flush()
        dev.timeout = save_timeout
      except device.DeviceError:
        # The device is no longer present.
        return

  # --- add arguments to parser   --------------------------------------------

  def add_args(self):
    """ Add arguments to parser. """

    self.parser.add_argument(
      'commands',
      metavar='COMMANDS',
      nargs='*',
      help="optional commands for the REPL. Use an '~' instead of ';' "
           "for multiple commands. Add an '~' to exit"
    )

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """repl [cmd [~ cmd ]... [~]]

      Enters into the regular REPL with the CircuitPython board.
      Use Control-X to exit REPL mode and return the shell. It may take
      a second or two before the REPL exits.

      If you provide commands to the REPL command, then they will be executed.
      If you want the REPL to exit, end the line with the ~ character.
    """

    dev = device.Device.get_device()
    if not dev:
      utils.print_err("no connected device")
      return

    cmds = self.parser.parse_args(args).commands
    if cmds and cmds[-1][-1] in ['~',';']:
      if cmds[-1] in ['~',';']:   # ~/; is distinct word
        cmds.pop()
      else:
        cmds[-1] = cmds[-1].rstrip('~;')  # remove trailing ~/;
      self._quit_when_no_output = True
    else:
      self._quit_when_no_output = False

    self.shell.print('Entering REPL. Use Control-%c to exit.' % QUIT_REPL_CHAR)
    self._quit_serial_reader = False
    self._serial_reader_running = AutoBool()
    repl_thread = threading.Thread(target=self._repl_serial_to_stdout,
                                   args=(dev,), name='REPL_serial_to_stdout')
    repl_thread.daemon = True
    repl_thread.start()
    # Wait for reader to start
    while not self._serial_reader_running():
      pass
    try:
      # Wake up the prompt
      dev.write(b'\r')
      if cmds:
        line = ' '.join(cmds).replace('~',';')
        dev.write(bytes(line, encoding='utf-8'))
        dev.write(b'\r')
      if not self._quit_when_no_output:
        while self._serial_reader_running():
          char = getch()
          if not char:
            continue
          if char == QUIT_REPL_BYTE:
            self._quit_serial_reader = True
            # When using telnet with the WiPy, it doesn't support
            # an initial timeout. So for the meantime, we send a
            # space which should cause the wipy to echo back a
            # space which will wakeup our reader thread so it will
            # notice the quit.
            dev.write(b' ')
            # Give the reader thread a chance to detect the quit
            # then we don't have to call getch() above again which
            # means we'd need to wait for another character.
            time.sleep(0.5)
            # Print a newline so that the cpshell prompt looks good.
            self.shell.print('')
            # We stay in the loop so that we can still enter
            # characters until we detect the reader thread quitting
            # (mostly to cover off weird states).
            continue
          if char == b'\n':
            dev.write(b'\r')
          else:
            dev.write(char)
    except device.DeviceError as err:
      # The device is no longer present.
      self.shell.print('')
      self.shell.stdout.flush()
      utils.print_err(err)
    repl_thread.join()
