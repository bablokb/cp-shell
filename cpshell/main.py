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

import binascii
import calendar
import fnmatch
import os
import re
import select
import serial
import socket
import tempfile
import time
import threading
from serial.tools import list_ports

if sys.platform == 'win32':
  EXIT_STR = 'Use the exit command to exit cpshell.'
else:
  EXIT_STR = 'Use Control-D (or the exit command) to exit cpshell.'

# I got the following from: http://www.farmckon.net/2009/08/rlcompleter-how-do-i-get-it-to-work/

MONTH = ('', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

# It turns out that just because pyudev is installed doesn't mean that
# it can actually be used. So we only bother to try if we're running
# under linux.
#
# When running under WSL, sys.platform returns 'linux' so we do a further check
# on 'Microsoft' in platform.uname().release to detect if we're running under WSL.
# Currently, there is no serial port enumeration availbale under WSL.
import platform
USE_AUTOCONNECT = sys.platform == 'linux' and 'Microsoft' not in platform.uname().release

SIX_MONTHS = 183 * 24 * 60 * 60

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

def align_cell(fmt, elem, width):
  """Returns an aligned element."""
  if fmt == "<":
    return elem + ' ' * (width - len(elem))
  if fmt == ">":
    return ' ' * (width - len(elem)) + elem
  return elem


def column_print(fmt, rows, print_func):
  """Prints a formatted list, adjusting the width so everything fits.
  fmt contains a single character for each column. < indicates that the
  column should be left justified, > indicates that the column should
  be right justified. The last column may be a space which implies left
  justification and no padding.

  """
  # Figure out the max width of each column
  num_cols = len(fmt)
  width = [max(0 if isinstance(row, str) else len(row[i]) for row in rows)
           for i in range(num_cols)]
  for row in rows:
    if isinstance(row, str):
      # Print a separator line
      print_func(' '.join([row * width[i] for i in range(num_cols)]))
    else:
      print_func(' '.join([align_cell(fmt[i], row[i], width[i])
                           for i in range(num_cols)]))


def find_macthing_files(match):
  """Finds all of the files which match (used for completion)."""
  last_slash = match.rfind('/')
  if last_slash == -1:
    dirname = '.'
    match_prefix = match
    result_prefix = ''
  else:
    dirname = match[0:last_slash]
    match_prefix = match[last_slash + 1:]
    result_prefix = dirname + '/'
  return [result_prefix + filename for filename in os.listdir(dirname) if filename.startswith(match_prefix)]


def is_pattern(s):
  """Return True if a string contains Unix wildcard pattern characters.
  """
  return not set('*?[{').intersection(set(s)) == set()


# Disallow patterns like path/t*/bar* because handling them on remote
# system is difficult without the glob library.
def parse_pattern(s):
  """Parse a string such as 'foo/bar/*.py'
  Assumes is_pattern(s) has been called and returned True
  1. directory to process
  2. pattern to match"""
  if '{' in s:
    return None, None  # Unsupported by fnmatch
  if s and s[0] == '~':
    s = os.path.expanduser(s)
  parts = s.split('/')
  absolute = len(parts) > 1 and not parts[0]
  if parts[-1] == '':  # # Outcome of trailing /
    parts = parts[:-1]  # discard
  if len(parts) == 0:
    directory = ''
    pattern = ''
  else:
    directory = '/'.join(parts[:-1])
    pattern = parts[-1]
  if not is_pattern(directory): # Check for e.g. /abc/*/def
    if is_pattern(pattern):
      if not directory:
        directory = '/' if absolute else '.'
      return directory, pattern
  return None, None # Invalid or nonexistent pattern

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


def cat(src_filename, dst_file):
  """Copies the contents of the indicated file to an already opened file."""
  (dev, dev_filename) = utils.get_dev_and_path(src_filename)
  if dev is None:
    with open(dev_filename, 'rb') as txtfile:
      for line in txtfile:
        dst_file.write(line)
  else:
    filesize = dev.remote_eval(get_filesize, dev_filename)
    return dev.remote(send_file_to_host, dev_filename, dst_file, filesize,
                      xfer_func=recv_file_from_remote)


def chdir(dirname):
  """Changes the current working directory."""
  import os
  os.chdir(dirname)


def copy_file(src_filename, dst_filename):
  """Copies a file from one place to another. Both the source and destination
    files must exist on the same machine.
  """
  try:
    with open(src_filename, 'rb') as src_file:
      with open(dst_filename, 'wb') as dst_file:
        while True:
          buf = src_file.read(BUFFER_SIZE)
          if len(buf) > 0:
            dst_file.write(buf)
          if len(buf) < BUFFER_SIZE:
            break
    return True
  except:
    return False


def cp(src_filename, dst_filename):
  """Copies one file to another. The source file may be local or remote and
    the destination file may be local or remote.
  """
  src_dev, src_dev_filename = utils.get_dev_and_path(src_filename)
  dst_dev, dst_dev_filename = utils.get_dev_and_path(dst_filename)

  main_options.verbose and print(f"cp {src_filename} {dst_filename}")
  if src_dev is dst_dev:
    # src and dst are either on the same remote, or both are on the host
    return utils.auto(copy_file, src_filename, dst_dev_filename)

  filesize = utils.auto(get_filesize, src_filename)

  if dst_dev is None:
    # Copying from remote to host
    with open(dst_dev_filename, 'wb') as dst_file:
      return src_dev.remote(send_file_to_host, src_dev_filename, dst_file,
                            filesize, xfer_func=recv_file_from_remote)
  if src_dev is None:
    # Copying from host to remote
    with open(src_dev_filename, 'rb') as src_file:
      return dst_dev.remote(recv_file_from_host, src_file, dst_dev_filename,
                            filesize, xfer_func=send_file_to_remote)

def eval_str(string):
  """Executes a string containing python code."""
  output = eval(string)
  return output

# 0x0D's sent from the host get transformed into 0x0A's, and 0x0A sent to the
# host get converted into 0x0D0A when using sys.stdin. sys.tsin.buffer does
# no transformations, so if that's available, we use it, otherwise we need
# to use hexlify in order to get unaltered data.

def recv_file_from_host(src_file, dst_filename, filesize, dst_mode='wb'):
  """Function which runs on the board. Matches up with send_file_to_remote."""
  import sys
  import binascii
  import os
  try:
    import time
    with open(dst_filename, dst_mode) as dst_file:
      bytes_remaining = filesize
      bytes_remaining *= 2  # hexlify makes each byte into 2
      buf_size = BUFFER_SIZE
      write_buf = bytearray(buf_size)
      read_buf = bytearray(buf_size)
      while bytes_remaining > 0:
        # Send back an ack as a form of flow control
        sys.stdout.write('\x06')
        read_size = min(bytes_remaining, buf_size)
        buf_remaining = read_size
        buf_index = 0
        while buf_remaining > 0:
          bytes_read = sys.stdin.readinto(read_buf, read_size)
          time.sleep(0.02)
          if bytes_read > 0:
            write_buf[buf_index:bytes_read] = read_buf[0:bytes_read]
            buf_index += bytes_read
            buf_remaining -= bytes_read
        dst_file.write(binascii.unhexlify(write_buf[0:read_size]))
        if hasattr(os, 'sync'):
          os.sync()
        bytes_remaining -= read_size
    return True
  except Exception as ex:
    print(ex)
    return False


def send_file_to_remote(dev, src_file, dst_filename, filesize, dst_mode='wb'):
  """Intended to be passed to the `remote` function as the xfer_func argument.
    Matches up with recv_file_from_host.
  """
  bytes_remaining = filesize
  save_timeout = dev.timeout
  dev.timeout = 2
  while bytes_remaining > 0:
    # Wait for ack so we don't get too far ahead of the remote
    ack = dev.read(1)
    if ack is None or ack != b'\x06':
      raise RuntimeError("timed out or error in transfer to remote: {!r}\n".format(ack))

    buf_size = main_options.buffer_size // 2
    read_size = min(bytes_remaining, buf_size)
    buf = src_file.read(read_size)
    #sys.stdout.write('\r%d/%d' % (filesize - bytes_remaining, filesize))
    #sys.stdout.flush()
    dev.write(binascii.hexlify(buf))
    bytes_remaining -= read_size
  #sys.stdout.write('\r')
  dev.timeout = save_timeout


def recv_file_from_remote(dev, src_filename, dst_file, filesize):
  """Intended to be passed to the `remote` function as the xfer_func argument.
    Matches up with send_file_to_host.
  """
  bytes_remaining = filesize
  bytes_remaining *= 2  # hexlify makes each byte into 2
  buf_size = main_options.buffer_size
  write_buf = bytearray(buf_size)
  while bytes_remaining > 0:
    read_size = min(bytes_remaining, buf_size)
    buf_remaining = read_size
    buf_index = 0
    while buf_remaining > 0:
      read_buf = dev.read(buf_remaining)
      bytes_read = len(read_buf)
      if bytes_read:
        write_buf[buf_index:bytes_read] = read_buf[0:bytes_read]
        buf_index += bytes_read
        buf_remaining -= bytes_read
    dst_file.write(binascii.unhexlify(write_buf[0:read_size]))
    # Send an ack to the remote as a form of flow control
    dev.write(b'\x06')   # ASCII ACK is 0x06
    bytes_remaining -= read_size


def send_file_to_host(src_filename, dst_file, filesize):
  """Function which runs on the board. Matches up with recv_file_from_remote."""
  import sys
  import binascii
  try:
    with open(src_filename, 'rb') as src_file:
      bytes_remaining = filesize
      buf_size = BUFFER_SIZE // 2
      while bytes_remaining > 0:
        read_size = min(bytes_remaining, buf_size)
        buf = src_file.read(read_size)
        sys.stdout.write(binascii.hexlify(buf))
        bytes_remaining -= read_size
        # Wait for an ack so we don't get ahead of the remote
        while True:
          char = sys.stdin.read(1)
          if char:
            if char == '\x06':
              break
            # This should only happen if an error occurs
            sys.stdout.write(char)
    return True
  except:
    return False

def word_len(word):
  """Returns the word length, minus any color codes."""
  if word[0] == '\x1b':
    return len(word) - 11   # 7 for color, 4 for no-color
  return len(word)


def print_cols(words, print_func, termwidth=79):
  """Takes a single column of words, and prints it as multiple columns that
  will fit in termwidth columns.
  """
  width = max([word_len(word) for word in words])
  nwords = len(words)
  ncols = max(1, (termwidth + 1) // (width + 1))
  nrows = (nwords + ncols - 1) // ncols
  for row in range(nrows):
    for i in range(row, nwords, nrows):
      word = words[i]
      if word[0] == '\x1b':
        print_func('%-*s' % (width + 11, words[i]),
                   end='\n' if i + nrows >= nwords else ' ')
      else:
        print_func('%-*s' % (width, words[i]),
                   end='\n' if i + nrows >= nwords else ' ')






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
      print('Welcome to cpshell.', EXIT_STR)
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
