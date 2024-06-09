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

from cpshell import ansi_colors
from cpshell.cplocale import CP_LOCALE

# --- query program defaults from environment   ------------------------------

def set_defaults(defaults):
  """ query defaults from the environment """

  defaults.port = os.getenv('CPSHELL_PORT')
  if not defaults.port:
    if os.path.exists('/dev/ttyUSB0'):
      defaults.port = '/dev/ttyUSB0'
    elif os.path.exists('/dev/ttyACM0'):
      defaults.port = '/dev/ttyACM0'

  try:
    defaults.baud = int(os.getenv('CPSHELL_BAUD'))
  except:
    defaults.baud = 115200

  try:
    defaults.buffer_size = int(os.getenv('CPSHELL_BUFFER_SIZE'))
  except:
    defaults.buffer_size = 32

  defaults.editor = (os.getenv('EDITOR') or os.getenv('CPSHELL_EDITOR') or
                     os.getenv('VISUAL') or 'vi')

  defaults.color   = sys.stdout.isatty()
  defaults.nocolor = not defaults.color
  defaults.debug   = False
  defaults.verbose = False

  try:
    defaults.host_locale = locale.getlocale()[0]
  except:
    defaults.host_locale = 'en_US'

# --- create parser for main program   ---------------------------------------

def create_parser(defaults):
  """ create and return parser """

  parser = argparse.ArgumentParser(
      prog="cpshell",
      usage="%(prog)s [options] [command]",
      description="Remote Shell for a CircuitPython board.",
      epilog=("You can specify the default serial port using the " +
              "CPSHELL_PORT environment variable.")
  )

  parser.add_argument(
      "-p", "--port",
      dest="port",
      help=f"Set the serial port to use (default: {defaults.port})",
      default=defaults.port
  )
  parser.add_argument(
      "-b", "--baud",
      dest="baud",
      action="store",
      type=int,
      help=f"Set the baudrate used (default: {defaults.baud:d})",
      default=defaults.baud
  )
  parser.add_argument(
      "-w", "--wait",
      dest="wait",
      type=int,
      action="store",
      help="Seconds to wait for serial port",
      default=0
  )
  parser.add_argument(
      "--buffer-size",
      dest="buffer_size",
      action="store",
      type=int,
      help="Set the low-level buffer size used for transfers "
           "(default: {defaults.buffer_size}",
      default=defaults.buffer_size
  )
  parser.add_argument(
      "-l", "--list",
      dest="list",
      action="store_true",
      help="Display serial ports",
      default=False
  )

  parser.add_argument(
      "-e", "--editor",
      dest="editor",
      help=f"Set the editor to use (default: {defaults.editor})",
      default=defaults.editor
  )
  parser.add_argument(
      "-n", "--nocolor",
      dest="nocolor",
      action="store_true",
      help="Turn off colorized output",
      default=defaults.nocolor
  )
  parser.add_argument(
      "-L", "--locale",
      dest="cp_locale",
      help=f"The language (locale) of the CP-device (default: {defaults.host_locale})",
      default=defaults.host_locale
  )

  parser.add_argument(
      "-f", "--file",
      dest="filename",
      help="Specifies a file of commands to process."
  )
  parser.add_argument(
    "-t", "--time",
    dest="upd_time",
    action='store_true',
    help="set time on device (default for shell/cp/rsync)",
    default=False
  )

  parser.add_argument(
      '-V', '--version',
      dest='version',
      action='store_true',
      help='Report the version and exit.',
      default=False
  )
  parser.add_argument(
      "-v", "--verbose",
      dest="verbose",
      action="store_true",
      help="Be verbose",
      default=False
  )
  parser.add_argument(
      "-T", "--timing",
      dest="timing",
      action="store_true",
      help="Print timing information about each command",
      default=False
  )
  parser.add_argument(
      "-d", "--debug",
      dest="debug",
      action="store_true",
      help="Enable debug output",
      default=False
  )
  parser.add_argument(
      "cmd",
      nargs=argparse.REMAINDER,
      help="Optional command to execute"
  )

  return parser

# --- validate and fix options   ---------------------------------------------

def check_options(options):
  """ validate and fix options """

  if not len(options.cmd) or 'cp' in options.cmd or 'rsync' in options.cmd:
    options.upd_time = True

  if options.debug:
    print(f"Port        = {options.port}")
    print(f"Baud        = {options.baud}")
    print(f"Wait        = {options.wait}")
    print(f"List        = {options.list}")
    print(f"time        = {options.upd_time}")
    print(f"nocolor     = {options.nocolor}")
    print(f"Timing      = {options.timing}")
    print(f"buffer_size = {options.buffer_size}")
    print(f"cp_locale   = {options.cp_locale}")
    print(f"Verbose     = {options.verbose}")
    print(f"Debug       = {options.debug}")
    print(f"Cmd         = [{', '.join(options.cmd)}]")

  if options.nocolor:
    options.dir_color = ''
    options.prompt_color = ''
    options.py_color = ''
    options.end_color = ''
  else:
    options.dir_color    = ansi_colors.LT_CYAN
    options.prompt_color = ansi_colors.LT_GREEN
    options.py_color     = ansi_colors.DK_GREEN
    options.end_color    = ansi_colors.NO_COLOR

  if sys.platform == 'darwin':
    # The readline that comes with OSX screws up colors in the prompt
    options.fake_input_prompt = True
  else:
    options.fake_input_prompt = False

  # we need the locale for the (localized) "soft reboot" message
  if options.cp_locale in CP_LOCALE:
    options.soft_reboot = CP_LOCALE[options.cp_locale]
  elif options.cp_locale.split("_")[0] in CP_LOCALE:
    options.soft_reboot = CP_LOCALE[options.cp_locale.split("_")[0]]
  else:
    options.soft_reboot = None
