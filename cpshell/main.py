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
try:
  from cpshell.getch import getch
  from cpshell.version import __version__
  from . import utils
  from . import device
except ImportError as err:
  print('sys.path =', sys.path)
  raise err

import calendar
import os
import re
import select
import socket
import tempfile
import time
import threading
from serial.tools import list_ports

# It turns out that just because pyudev is installed doesn't mean that
# it can actually be used. So we only bother to try if we're running
# under linux.
#
# When running under WSL, sys.platform returns 'linux' so we do a further check
# on 'Microsoft' in platform.uname().release to detect if we're running under WSL.
# Currently, there is no serial port enumeration availbale under WSL.
import platform
USE_AUTOCONNECT = sys.platform == 'linux' and 'Microsoft' not in platform.uname().release

QUIT_REPL_CHAR = 'X'
QUIT_REPL_BYTE = bytes((ord(QUIT_REPL_CHAR) - ord('@'),))  # Control-X

TIME_OFFSET = 0

def is_circuitpython_usb_device(port):
  """Checks a USB device to see if it looks like a CircuitPython device.
  """
  if type(port).__name__ == 'Device':
    # Assume its a pyudev.device.Device
    if ('ID_BUS' not in port or port['ID_BUS'] != 'usb' or
        'SUBSYSTEM' not in port or port['SUBSYSTEM'] != 'tty'):
      return False
    usb_id = 'usb vid:pid={}:{}'.format(port['ID_VENDOR_ID'], port['ID_MODEL_ID'])
  else:
    # Assume its a port from serial.tools.list_ports.comports()
    usb_id = port[2].lower()
  # We don't check the last digit of the PID since there are 3 possible
  # values.
  if usb_id.startswith('usb vid:pid=f055:980'):
    return True
  # Check Raspberry Pi Pico
  if usb_id.startswith('usb vid:pid=2e8a:0005'):
    return True
  # Check for Teensy VID:PID
  if usb_id.startswith('usb vid:pid=16c0:0483'):
    return True
  # Check for LEGO Technic Large Hub
  if usb_id.startswith('usb vid:pid=0694:0010'):
    return True
  return False


def is_circuitpython_usb_port(portName):
  """Checks to see if the indicated portname is a CircuitPython device
    or not.
  """
  for port in serial.tools.list_ports.comports():
    if port.device == portName:
      return is_circuitpython_usb_device(port)
  return False


def autoconnect():
  """Sets up a thread to detect when USB devices are plugged and unplugged.
    If the device looks like a CircuitPython board, then it will automatically
    connect to it.
  """
  if not USE_AUTOCONNECT:
    return
  try:
    import pyudev
  except ImportError:
    return
  context = pyudev.Context()
  monitor = pyudev.Monitor.from_netlink(context)
  connect_thread = threading.Thread(target=autoconnect_thread, args=(monitor,), name='AutoConnect')
  connect_thread.daemon = True
  connect_thread.start()


def autoconnect_thread(monitor):
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
        dev = find_serial_device_by_port(usb_dev.device_node)
        if usb_dev.action == 'add':
          # Try connecting a few times. Sometimes the serial port
          # reports itself as busy, which causes the connection to fail.
          for i in range(8):
            if dev:
              connected = connect(dev.port, dev.baud, dev.wait)
            elif is_circuitpython_usb_device(usb_dev):
              connected = connect(usb_dev.device_node)
            else:
              connected = False
            if connected:
              break
            time.sleep(0.25)
        elif usb_dev.action == 'remove':
          print('')
          print("USB Serial device '%s' disconnected" % usb_dev.device_node)
          if dev:
            dev.close()
            break


def autoscan():
  """autoscan will check all of the serial ports to see if they have
    a matching VID:PID for a CircuitPython board.
  """
  for port in serial.tools.list_ports.comports():
    if is_circuitpython_usb_device(port):
      connect(port[0])


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
  for port in serial.tools.list_ports.comports():
    detected = True
    if port.vid:
      cpport = ''
      if is_circuitpython_usb_device(port):
        #print(f"is_circuitpython_usb_device!")
        cpport = ' *'
      print('USB Serial Device {:04x}:{:04x}{} found @{}{}\r'.format(
            port.vid, port.pid,
            extra_info(port), port.device, cpport))
    else:
      print('Serial Device:', port.device)
  if not detected:
    print('No serial devices detected')


def print_bytes(byte_str):
  """Prints a string or converts bytes to a string and then prints."""
  if isinstance(byte_str, str):
    print(byte_str)
  else:
    print(str(byte_str, encoding='utf8'))

def board_name(default):
  """Returns the boards name (if available)."""
  import board
  return repr(board.board_id)



def eval_str(string):
  """Executes a string containing python code."""
  output = eval(string)
  return output

def add_arg(*args, **kwargs):
  """Returns a list containing args and kwargs."""
  return (args, kwargs)

def connect(port, baud=115200, wait=0):
  """Connect to a CircuitPython board via a serial port."""
  main_options.debug and print(
    'Connecting to %s (buffer-size %d)...' % (port, main_options.buffer_size))
  try:
    dev = device.DeviceSerial(main_options,port, baud, wait)
  except device.DeviceError as err:
    sys.stderr.write(str(err))
    sys.stderr.write('\n')
    return False
  device.Device.set_device(dev)
  return True


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
      connect(options.port, baud=options.baud, wait=options.wait)
    except Exception as ex:
      main_options.debug and print(ex)
      raise
  else:
    autoscan()
  autoconnect()

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

# --- main program   ---------------------------------------------------------

if __name__ == "__main__":
  if sys.platform == 'win32':
    # This is a workaround for Windows 10/Python 3.7, that allows the
    # colorized output to work.
    # See: https://stackoverflow.com/questions/12492810/python-how-can-i-make-the-ansi-escape-codes-to-work-also-in-windows
    import subprocess
    subprocess.call('', shell=True)

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
