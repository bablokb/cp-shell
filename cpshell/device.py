# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Device classes
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

import time
import inspect
import token
import tokenize
import io
import serial

from .cpboard import CpBoard, CpBoardError
from . import utils

def strip_source(source):
  """ Strip out comments and Docstrings from some python source code."""
  mod = ""

  prev_toktype = token.INDENT
  last_lineno = -1
  last_col = 0

  tokgen = tokenize.generate_tokens(io.StringIO(source).readline)
  for toktype, ttext, (slineno, scol), (elineno, ecol), ltext in tokgen:
    if 0:   # Change to if 1 to see the tokens fly by.
      print("%10s %-14s %-20r %r" % (
          tokenize.tok_name.get(toktype, toktype),
          "%d.%d-%d.%d" % (slineno, scol, elineno, ecol),
          ttext, ltext
          ))
    if slineno > last_lineno:
      last_col = 0
    if scol > last_col:
      mod += " " * (scol - last_col)
    if toktype == token.STRING and prev_toktype == token.INDENT:
      # Docstring
      mod = mod.rstrip(' \t\n')
    elif toktype == tokenize.COMMENT:
      # Comment
      mod = mod.rstrip(' \t\n')
    else:
      mod += ttext
    prev_toktype = toktype
    last_col = ecol
    last_lineno = elineno
  return mod

def remote_repr(i):
  """Helper function to deal with types which we can't send to the board."""
  repr_str = repr(i)
  if repr_str and repr_str[0] == '<':
    return 'None'
  return repr_str

class DeviceError(Exception):
  """Errors that we want to report to the user and keep running."""
  pass

class Device(object):

  _device = None

  @classmethod
  def set_device(cls,dev):
    """ set the (singleton) device """
    if cls._device:
      cls._device.close()
    cls._device = dev
    cls._device.name_path = '/' + dev.name + '/'

  @classmethod
  def get_device(cls):
    """ return singleton device """
    return cls._device

  # --- constructor   --------------------------------------------------------

  def __init__(self,options,cpb=None):
    self.options = options
    self.cpb = cpb

  # --- setup of the device   ------------------------------------------------

  def setup(self):
    """ initial setup of the device after connect """

    #self.sysname = ''
    #self.options.verbose and print('Retrieving sysname ... ', end='', flush=True)
    #self.sysname = self.remote_eval(sysname)
    #self.options.verbose and print(self.sysname)

    self.options.debug and print('Retrieving root directories ... ', end='', flush=True)
    self.root_dirs = ['/{}/'.format(dir) for dir in self.remote_eval(utils.listdir, '/')]
    self.options.debug and print(' '.join(self.root_dirs))

    if self.options.upd_time:
      self.options.verbose and print('Setting time ... ', end='', flush=True)
      now = self.sync_time()
      self.options.verbose and print(time.strftime('%b %d, %Y %H:%M:%S', now))

    #self.options.verbose and print('Evaluating board_name ... ', end='', flush=True)
    #self.name, messages = self.remote_eval_last(board_name, self.default_board_name())
    #self.options.verbose and print(self.name)
    #if (len(messages) > 0) and self.options.verbose:
    #  print('----- Prints from board.py ----')
    #  print(messages)
    #  print('----')
    #self.dev_name_short = self.name

  def check_cpb(self):
    """Raises an error if the cpb object was closed."""
    if self.cpb is None:
      raise DeviceError('serial port %s closed' % self.dev_name_short)

  def close(self):
    """Closes the serial port."""
    if self.cpb and self.cpb.serial:
      self.cpb.serial.close()
    self.cpb = None

  def default_board_name(self):
    return 'unknown'

  def is_root_path(self, filename):
    """Determines if 'filename' corresponds to a directory on this device."""
    test_filename = filename + '/'
    for root_dir in self.root_dirs:
      if test_filename.startswith(root_dir):
        return True
    return False

  def is_serial_port(self, port):
    return False

  def read(self, num_bytes):
    """Reads data from the board over the serial port."""
    self.check_cpb()
    try:
      return self.cpb.serial.read(num_bytes)
    except (serial.serialutil.SerialException, TypeError):
      # Write failed - assume that we got disconnected
      self.close()
      raise DeviceError('serial port %s closed' % self.dev_name_short)

  def remote(self, func, *args, xfer_func=None, **kwargs):
    """Calls func with the indicated args on the CircuitPython board."""
    if hasattr(func, 'extra_funcs'):
      func_name = func.name
      func_lines = []
      for extra_func in func.extra_funcs:
        func_lines += inspect.getsource(extra_func).split('\n')
        func_lines += ['']
      func_lines += filter(lambda line: line[:1] != '@', func.source.split('\n'))
      func_src = '\n'.join(func_lines)
    else:
      func_name = func.__name__
      func_src = inspect.getsource(func)
    func_src = strip_source(func_src)
    args_arr = [remote_repr(i) for i in args]
    kwargs_arr = ["{}={}".format(k, remote_repr(v)) for k, v in kwargs.items()]
    func_src += 'try:\n'
    func_src += '  output = ' + func_name + '('
    func_src += ', '.join(args_arr + kwargs_arr)
    func_src += ')\n'
    func_src += 'except Exception as ex:\n'
    func_src += '  print(ex)\n'
    func_src += '  output = None\n'
    func_src += 'if output is None:\n'
    func_src += '  print("None")\n'
    func_src += 'else:\n'
    func_src += '  print(output)\n'
    func_src = func_src.replace('BUFFER_SIZE', str(self.options.buffer_size))
    if self.options.debug:
      print(
        '----- About to send %d bytes of code to the board -----' % len(func_src))
      print(func_src)
      print('-----')
    self.check_cpb()
    try:
      self.cpb.enter_raw_repl()
      #print("in raw repl")
      self.check_cpb()
      output = self.cpb.exec_raw_no_follow(func_src)
      if xfer_func:
        xfer_func(self, *args, **kwargs)
      self.check_cpb()
      output, _ = self.cpb.follow(timeout=20)
      self.check_cpb()
      self.cpb.exit_raw_repl()
      if self.options.debug:
        print('-----Response-----')
        print(output)
        print('------------------')
      return output
    except (serial.serialutil.SerialException, TypeError):
      raise DeviceError('serial port %s closed' % self.dev_name_short)
    except:
      self.cpb.exit_raw_repl()
      self.close()
      raise

  def remote_eval(self, func, *args, **kwargs):
    """Calls func with the indicated args on the CircuitPython board, and
      converts the response back into python by using eval.
    """
    return eval(self.remote(func, *args, **kwargs))

  def remote_eval_last(self, func, *args, **kwargs):
    """Calls func with the indicated args on the CircuitPython board, and
      converts the response back into python by using eval.
    """
    result = self.remote(func, *args, **kwargs).split(b'\r\n')
    #print(f"===> {result=}")
    messages = result[0:-2]
    messages = b'\n'.join(messages).decode('utf-8')
    #print(f"===> {messages=}")
    if len(result) >= 2:
      return (eval(result[-2]), messages)
    else:
      return("",messages)

  def status(self):
    """Returns a status string to indicate whether we're connected to
      the board or not.
    """
    if self.cpb is None:
      return 'closed'
    return 'connected'

  def sync_time(self):
    """Sets the time on the board to match the time on the host."""
    now = time.localtime(time.time())
    self.remote(utils.set_time, (now.tm_year, now.tm_mon, now.tm_mday,
                           now.tm_hour, now.tm_min, now.tm_sec,
                           now.tm_wday, -1, -1))
    return now

  def write(self, buf):
    """Writes data to the board over the serial port."""
    self.check_cpb()
    try:
      return self.cpb.serial.write(buf)
    except (serial.serialutil.SerialException, BrokenPipeError, TypeError):
      # Write failed - assume that we got disconnected
      self.close()
      raise DeviceError('{} closed'.format(self.dev_name_short))

# --- serial device   --------------------------------------------------------

class DeviceSerial(Device):

  def __init__(self,options,port,baud,wait):
    super().__init__(options)
    self.port = port
    self.baud = baud
    self.wait = wait

    if wait and not os.path.exists(port):
      toggle = False
      try:
        if self.options.verbose:
          sys.stdout.write("Waiting %d seconds for serial port '%s' to exist" % (wait, port))
          sys.stdout.flush()
        while wait and not os.path.exists(port):
          if self.options.verbose:
            sys.stdout.write('.')
            sys.stdout.flush()
          time.sleep(0.5)
          toggle = not toggle
          wait = wait if not toggle else wait -1
        self.options.verbose and sys.stdout.write("\n")
      except KeyboardInterrupt:
        raise DeviceError('Interrupted')

    self.name = port
    self.dev_name_long = '%s at %d baud' % (port, baud)

    try:
      self.cpb = CpBoard(port, baudrate=baud, wait=wait,
                    soft_reboot=self.options.soft_reboot)
    except CpBoardError as err:
      print(err)
      sys.exit(1)

    # Bluetooth devices take some time to connect at startup, and writes
    # issued while the remote isn't connected will fail. So we send newlines
    # with pauses until one of our writes succeeds.
    try:
      # we send a Control-C which should kill the current line
      # assuming we're talking to the CircuitPython repl. If we send
      # a newline, then the junk might get interpreted as a command
      # which will do who knows what.
      self.cpb.serial.write(b'\x03')
    except serial.serialutil.SerialException:
      # Write failed. Now report that we're waiting and keep trying until
      # a write succeeds
      self.options.verbose and sys.stdout.write("Waiting for transport to be connected.")
      while True:
        time.sleep(0.5)
        try:
          self.cpb.serial.write(b'\x03')
          break
        except serial.serialutil.SerialException:
          pass
        if self.options.verbose:
          sys.stdout.write('.')
          sys.stdout.flush()
      self.options.verbose and sys.stdout.write('\n')

    # Send Control-C followed by CR until we get a >>> prompt
    self.options.verbose and print('Trying to connect to REPL ', end='', flush=True)
    connected = False
    for _ in range(20):
      self.cpb.serial.write(b'\x03\r')
      data = self.cpb.read_until(1, b'>>> ', timeout=0.1)
      if data.endswith(b'>>> '):
        connected = True
        break
      if self.options.verbose:
        sys.stdout.write('.')
        sys.stdout.flush()
    if connected:
      self.options.verbose and print(' connected', flush=True)
    else:
      raise DeviceError('Unable to connect to REPL')

    # In theory the serial port is now ready to use
    self.setup()
    self.dev_name_short = port

  def default_board_name(self):
    return 'cpboard'

  def is_serial_port(self, port):
    return self.dev_name_short == port

  @property
  def timeout(self):
    """Gets the timeout associated with the serial port."""
    self.check_cpb()
    return self.cpb.serial.timeout

  @timeout.setter
  def timeout(self, value):
    """Sets the timeout associated with the serial port."""
    self.check_cpb()
    try:
      self.cpb.serial.timeout = value
    except:
      # timeout is a property so it calls code, and that can fail
      # if the serial port is closed.
      pass
