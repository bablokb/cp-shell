# -------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Besides some changes necessary due to CircuitPython, I also removed some
# code specific to MicroPython and everything related to telnet. In addition,
# there was some streamlining done.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# -------------------------------------------------------------------------

"""Implement a remote shell which talks to a CircuitPython board.

  This program uses the raw-repl feature of the board to send small
  programs to the board to carry out the required tasks.
"""

# Take a look at https://repolinux.wordpress.com/2012/10/09/non-blocking-read-from-stdin-in-python/
# to see if we can use those ideas here.

# from __future__ import print_function

# To run cpshell from the git repository, cd into the top level cpshell directory
# and run:
#   python3 -m cpshell.main
#
# that sets things up so that the "from cpshell.xxx" will import from the git
# tree and not from some installed version.

import sys
import traceback
import select
import time
import threading
import locale
from serial.tools import list_ports

try:
  from cpshell.getch import getch
  from cpshell.version import __version__
  from . import utils
  from . import device
except ImportError as err:
  print('sys.path =', sys.path)
  raise err

def is_tty_usb_device(port):
  """Checks a USB device to see if it looks like a tty device.
  """
  if type(port).__name__ == 'Device':
    # Assume its a pyudev.device.Device
    if port.get('ID_BUS') != 'usb' or getattr(port,'subsystem','') != 'tty':
      return False
  return True

def autoconnect(debug):
  """Sets up a thread to detect when USB devices are plugged and unplugged.
    If the device looks like a CircuitPython board, then it will automatically
    connect to it.
  """
  try:
    import pyudev
  except ImportError:
    return
  context = pyudev.Context()
  monitor = pyudev.Monitor.from_netlink(context)
  connect_thread = threading.Thread(target=autoconnect_thread,
                                    args=(monitor,debug,), name='AutoConnect')
  connect_thread.daemon = True
  connect_thread.start()


def autoconnect_thread(monitor,debug):
  """Thread which detects USB Serial devices connecting and disconnecting."""
  monitor.start()
  monitor.filter_by('tty')

  epoll = select.epoll()
  epoll.register(monitor.fileno(), select.POLLIN)

  while True:
    try:
      events = epoll.poll()
    except InterruptedError:
      continue
    for fileno, _ in events:
      if fileno == monitor.fileno():
        usb_dev = monitor.poll()
        print('autoconnect: {} action: {}'.format(usb_dev.device_node, usb_dev.action))
        dev = device.Device.get_device()
        if usb_dev.action == 'add':
          # Try connecting a few times. Sometimes the serial port
          # reports itself as busy, which causes the connection to fail.
          for i in range(8):
            if is_tty_usb_device(usb_dev):
              connected = utils.connect(usb_dev.device_node)   # will close old device
            else:
              connected = False
            if connected:
              break
            time.sleep(0.25)
        elif usb_dev.action == 'remove':
          print('')
          print("USB Serial device '%s' disconnected" % usb_dev.device_node)
          if dev and dev.port == usb_dev.device_node:
            dev.close()
            utils.print_debug(f"closing {dev.port}")
            break

def autoscan(debug):
  """autoscan will connect to the first available tty-port
  """
  for port in list_ports.comports():
    try:
      utils.connect(port[0])
    except:
      utils.print_err(f"could not connect to {port[0]}")
      debug and traceback.print_exc()

def extra_info(port):
  """Collects the serial nunber and manufacturer into a string, if
    the fields are available."""
  extra_items = []
  if port.manufacturer:
    extra_items.append("vendor '{}'".format(port.manufacturer))
  if port.serial_number:
    extra_items.append("serial '{}'".format(port.serial_number))
  if port.interface:
    extra_items.append("intf '{}'".format(port.interface))
  if extra_items:
    return ' with ' + ' '.join(extra_items)
  return ''


def listports():
  """listports will display a list of all of the serial ports.
  """
  detected = False
  for port in list_ports.comports():
    detected = True
    if port.vid:
      cpport = ' *'
      print('USB Serial Device {:04x}:{:04x}{} found @{}{}\r'.format(
            port.vid, port.pid,
            extra_info(port), port.device, cpport))
    else:
      print('Serial Device:', port.device)
  if not detected:
    print('No serial devices detected')

def eval_str(string):
  """Executes a string containing python code."""
  output = eval(string)
  return output

def add_arg(*args, **kwargs):
  """Returns a list containing args and kwargs."""
  return (args, kwargs)

# --- run according to options   ---------------------------------------------

def run(options):
  if options.version:
    print(__version__)
    return

  if options.list:
    listports()
    return

  if options.port:
    try:
      utils.connect(options.port, baud=options.baud, wait=options.wait)
    except Exception as ex:
      utils.print_debug(ex)
      raise
  else:
    options.autoconnect and autoscan(options.debug)
  options.autoconnect and autoconnect(options.debug)

  from .cmdshell import CmdShell
  if options.filename:
    with open(options.filename) as cmd_file:
      shell = CmdShell(options,stdin=cmd_file)
      shell.cmdloop('')
  else:
    cmd_line = ' '.join(options.cmd)
    if cmd_line == '':
      print('Welcome to cpshell.', utils.EXIT_STR)
    if not device.Device.get_device():
      print('')
      print('No boards connected - use the connect command to add one')
      print('')
    shell = CmdShell(options)
    try:
      shell.cmdloop(cmd_line)
    except KeyboardInterrupt:
      print('')

# --- main-function   --------------------------------------------------------

def main():
  if sys.platform == 'win32':
    # This is a workaround for Windows 10/Python 3.7, that allows the
    # colorized output to work.
    # See: https://stackoverflow.com/questions/12492810/python-how-can-i-make-the-ansi-escape-codes-to-work-also-in-windows
    import subprocess
    subprocess.call('', shell=True)

  # set local to default from environment
  locale.setlocale(locale.LC_ALL, '')

  save_settings = None
  stdin_fd = -1
  try:
    import termios
    stdin_fd = sys.stdin.fileno()
    save_settings = termios.tcgetattr(stdin_fd)
  except:
    pass
  try:
    from cpshell.main_parser import MainArgParser
    parser = MainArgParser()
    parser.create_parser()
    parser.parse_and_check()
    main_options = parser.options
    run(main_options)
  except KeyboardInterrupt:
    print()
  except Exception as ex:
    print(f"{ex.args[0]}")
    raise
  finally:
    if save_settings:
      termios.tcsetattr(stdin_fd, termios.TCSANOW, save_settings)

# --- main program   ---------------------------------------------------------

if __name__ == "__main__":
  # this indirection is necessary because of setuptools
  main()
