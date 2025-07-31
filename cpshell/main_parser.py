# -------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Helper functions for the main-program.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# -------------------------------------------------------------------------

import sys
import os
import argparse
import locale
import platform

from cpshell import ansi_colors
from cpshell.cplocale import CP_LOCALE
from cpshell.options import Options
from cpshell import utils


# --- Wrapper class for argparser   ------------------------------------------

class MainArgParser:
  """ maintain defaults and parse arguments """

  def __init__(self):
    """ constructor """
    self._set_defaults()

  # --- query program defaults from environment   ----------------------------

  def _set_defaults(self):
    """ query defaults from the environment """

    self._port = os.getenv('CPSHELL_PORT')
    if not self._port:
      if os.path.exists('/dev/ttyUSB0'):
        self._port = '/dev/ttyUSB0'
      elif os.path.exists('/dev/ttyACM0'):
        self._port = '/dev/ttyACM0'

    try:
      self._baud = int(os.getenv('CPSHELL_BAUD'))
    except:
      self._baud = 115200

    try:
      self._buffer_size = int(os.getenv('CPSHELL_BUFFER_SIZE'))
    except:
      self._buffer_size = 32

    self._chunk_size = 64
    self._chunk_wait = 0.5

    self._editor = (os.getenv('EDITOR') or os.getenv('CPSHELL_EDITOR') or
                       os.getenv('VISUAL') or 'vi')

    self._color   = sys.stdout.isatty()
    self._nocolor = not self._color
    self.debug    = False
    self.quiet    = False

    try:
      self._host_locale = locale.getlocale()[0]
    except:
      self._host_locale = 'en_US'

    # It turns out that just because pyudev is installed doesn't mean that
    # it can actually be used. So we only bother to try if we're running
    # under linux.
    #
    # When running under WSL, sys.platform returns 'linux' so we do a
    # further check on 'Microsoft' in platform.uname().release to detect
    # if we're running under WSL.
    # Currently, there is no serial port enumeration availbale under WSL.
    self._autoconnect = (sys.platform == 'linux' and
                         'Microsoft' not in platform.uname().release)

  # --- create parser for main program   -------------------------------------

  def create_parser(self):
    """ create and return parser """

    self._parser = argparse.ArgumentParser(
        prog="cpshell",
        usage="%(prog)s [options] [command]",
        description="Remote Shell for a CircuitPython board.",
        epilog=("You can specify the default serial port using the " +
                "CPSHELL_PORT environment variable.")
    )

    self._parser.add_argument(
        "-p", "--port",
        dest="port",
        help=f"Set the serial port to use (default: {self._port})",
        default=self._port
    )
    self._parser.add_argument(
        "-b", "--baud",
        dest="baud",
        action="store",
        type=int,
        help=f"Set the baudrate to use (default: {self._baud:d})",
        default=self._baud
    )
    self._parser.add_argument(
        "-w", "--wait",
        dest="wait",
        type=int,
        action="store",
        help="Seconds to wait for serial port (default: 0)",
        default=0
    )
    self._parser.add_argument(
        "-W", "--wait-repl",
        dest="wait_repl",
        type=float,
        action="store",
        help="Seconds to wait for connection with REPL (defaut: 2)",
        default=2
    )
    self._parser.add_argument(
        "--buffer-size",
        dest="buffer_size",
        action="store",
        type=int,
        help=f"Set the low-level serial buffer size "
             f"(default: {self._buffer_size})",
        default=self._buffer_size
    )
    self._parser.add_argument(
        "--chunk-size",
        dest="chunk_size",
        action="store",
        type=int,
        help=f"Set the low-level chunk size used for transfers "
             f"(default: {self._chunk_size})",
        default=self._chunk_size
    )
    self._parser.add_argument(
        "--chunk-wait",
        dest="chunk_wait",
        action="store",
        type=float,
        help=f"Set the wait-time in seconds between chunk transfers "
             f"(default: {self._chunk_wait})",
        default=self._chunk_wait
    )
    self._parser.add_argument(
        "--no-autoconnect",
        dest="autoconnect",
        action="store_false",
        help=f"don't autoconnect (default: autoconnect={self._autoconnect})",
        default=self._autoconnect
    )
    self._parser.add_argument(
        "-l", "--list",
        dest="list",
        action="store_true",
        help="Display serial ports",
      default=False
    )

    self._parser.add_argument(
        "-e", "--editor",
        dest="editor",
        help=f"Set the editor to use (default: {self._editor})",
        default=self._editor
    )
    self._parser.add_argument(
        "-n", "--nocolor",
        dest="nocolor",
        action="store_true",
        help="Turn off colorized output",
        default=self._nocolor
    )
    self._parser.add_argument(
        "-L", "--locale",
        dest="cp_locale",
        help=f"The language (locale) of the CP-device "
             f"(default: {self._host_locale})",
        default=self._host_locale
    )

    self._parser.add_argument(
        "-f", "--file",
        dest="filename",
        help="Specifies a file of commands to process."
    )
    self._parser.add_argument(
      "-t", "--time",
      dest="upd_time",
      action='store_true',
      help="set time on device (default for shell/cp/rsync)",
      default=False
    )

    self._parser.add_argument(
        '-V', '--version',
        dest='version',
        action='store_true',
        help='Report the version and exit.',
        default=False
    )
    self._parser.add_argument(
        "-q", "--quiet",
        dest="verbose",
        action="store_false",
        help="Be quiet (default: False)",
        default=True                       # quiet == not verbose
    )
    self._parser.add_argument(
        "-T", "--timing",
        dest="timing",
        action="store_true",
        help="Print timing information about each command",
        default=False
    )
    self._parser.add_argument(
        "-d", "--debug",
        dest="debug",
        action="store_true",
        help="Enable debug output",
        default=False
    )
    self._parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="Optional command to execute"
    )

  # --- validate and fix options   -------------------------------------------

  def parse_and_check(self):
    """ parse, validate and fix options """

    # parse commandline
    self.options = self._parser.parse_args(namespace=Options.get())
    if (not len(self.options.cmd) or
        self.options.cmd[0] in ['cp','rsync','edit','date']):
      self.options.upd_time = True

    if not self.options.autoconnect:
      self.options.port = None

    if self.options.debug:
      utils.print_err(f"port        = {self.options.port}")
      utils.print_err(f"baud        = {self.options.baud}")
      utils.print_err(f"wait        = {self.options.wait}")
      utils.print_err(f"chunk-size  = {self.options.chunk_size}")
      utils.print_err(f"chunk-wait  = {self.options.chunk_wait}")
      utils.print_err(f"autoconnect = {self.options.autoconnect}")
      utils.print_err(f"List        = {self.options.list}")
      utils.print_err(f"time        = {self.options.upd_time}")
      utils.print_err(f"nocolor     = {self.options.nocolor}")
      utils.print_err(f"Timing      = {self.options.timing}")
      utils.print_err(f"buffer_size = {self.options.buffer_size}")
      utils.print_err(f"cp_locale   = {self.options.cp_locale}")
      utils.print_err(f"quiet       = {not self.options.verbose}")
      utils.print_err(f"debug       = {self.options.debug}")
      utils.print_err(f"Cmd         = [{', '.join(self.options.cmd)}]")

    if self.options.nocolor:
      self.options.dir_color = ''
      self.options.prompt_color = ''
      self.options.py_color = ''
      self.options.end_color = ''
    else:
      self.options.dir_color    = ansi_colors.LT_CYAN
      self.options.prompt_color = ansi_colors.LT_GREEN
      self.options.py_color     = ansi_colors.DK_GREEN
      self.options.end_color    = ansi_colors.NO_COLOR

    if sys.platform == 'darwin':
      # The readline that comes with OSX screws up colors in the prompt
      self.options.fake_input_prompt = True
    else:
      self.options.fake_input_prompt = False

    # we need the locale for the (localized) "soft reboot" message
    if self.options.cp_locale in CP_LOCALE:
      self.options.soft_reboot = CP_LOCALE[self.options.cp_locale]
    elif self.options.cp_locale.split("_")[0] in CP_LOCALE:
      self.options.soft_reboot = CP_LOCALE[self.options.cp_locale.split("_")[0]]
    else:
      self.options.soft_reboot = b'soft reboot\r\n'
