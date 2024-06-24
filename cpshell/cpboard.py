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

"""
cpboard interface

This module provides the CpBoard class, used to communicate with and
control the board over a serial USB connection.

Example usage:

  import cpboard
  cpb = cpboard.CpBoard('/dev/ttyACM0')

Then:

  cpb.enter_raw_repl()
  cpb.exec('import board; print(board.board_id)')
  cpb.exit_raw_repl()

To run a script from the local machine on the board and print out the results:

  import cpboard
  cpboard.execfile('test.py', port='/dev/ttyACM0')

This script can also be run directly.  To execute a local script, use:

  ./cpboard.py test.py

Or:

  python3 cpboard.py test.py

"""

import sys
import time

stdout = sys.stdout.buffer

def stdout_write_bytes(b):
  b = b.replace(b"\x04", b"")
  stdout.write(b)
  stdout.flush()

class CpBoardError(Exception):
  pass

def parse_bool(str):
  return str == '1' or str.lower() == 'true'

class CpBoard:
  def __init__(self, port, baudrate=115200, wait=0, options=None):
    self._options = options
    import serial
    delayed = False
    self.serial = serial.Serial(baudrate=baudrate, inter_byte_timeout=1)

    self.serial.port = port
    for attempt in range(wait + 1):
      try:
        # Assigning the port attribute will attempt to open the port
        self.serial.open()
        break
      except (OSError, IOError): # Py2 and Py3 have different errors
        if wait == 0:
          continue
        if attempt == 0:
          sys.stdout.write(f'Waiting {wait} seconds for board ')
          delayed = True
      time.sleep(1)
      sys.stdout.write('.')
      sys.stdout.flush()
    else:
      if delayed:
        print('')
      raise CpBoardError('failed to access ' + port)
    if delayed:
      print('')

  def close(self):
    self.serial.close()

  def read_until(self, min_num_bytes, ending, timeout=10, data_consumer=None):
    data = self.serial.read(min_num_bytes)
    if data_consumer:
      data_consumer(data)
    timeout_count = 0
    while True:
      if data.endswith(ending):
        break
      elif self.serial.inWaiting() > 0:
        new_data = self.serial.read(1)
        data = data + new_data
        if data_consumer:
          data_consumer(new_data)
        timeout_count = 0
      else:
        timeout_count += 1
        if timeout is not None and timeout_count >= 100 * timeout:
          break
        time.sleep(0.01)
    return data

  def enter_raw_repl(self):
    #print("2x CTRL-C")
    self.serial.write(b'\r\x03\x03') # ctrl-C twice: interrupt any running program

    # flush input (without relying on serial.flushInput())
    n = self.serial.inWaiting()
    while n > 0:
      self.serial.read(n)
      n = self.serial.inWaiting()

    #print("CTRL-A")
    self.serial.write(b'\r\x01') # ctrl-A: enter raw REPL
    data = self.read_until(1, b'raw REPL; CTRL-B to exit\r\n>')
    if not data.endswith(b'raw REPL; CTRL-B to exit\r\n>'):
      print(data)
      raise CpBoardError('could not enter raw repl')

    #print("CTRL-D")
    self.serial.write(b'\x04') # ctrl-D: soft reset
    data = self.read_until(1,self._options.soft_reboot,timeout=1)
    if not data.endswith(self._options.soft_reboot):
      #print(data)
      raise CpBoardError('could not enter raw repl')
    # By splitting this into 2 reads, it allows boot.py to print stuff,
    # which will show up after the soft reboot and before the raw REPL.
    data = self.read_until(1, b'raw REPL; CTRL-B to exit\r\n')
    if not data.endswith(b'raw REPL; CTRL-B to exit\r\n'):
      print(data)
      raise CpBoardError('could not enter raw repl')

  def exit_raw_repl(self):
    self.serial.write(b'\r\x02') # ctrl-B: enter friendly REPL

  def follow(self, timeout, data_consumer=None):
    # wait for normal output
    data = self.read_until(1, b'\x04', timeout=timeout, data_consumer=data_consumer)
    if not data.endswith(b'\x04'):
      raise CpBoardError('timeout waiting for first EOF reception')
    data = data[:-1]

    # wait for error output
    data_err = self.read_until(1, b'\x04', timeout=timeout)
    if not data_err.endswith(b'\x04'):
      raise CpBoardError('timeout waiting for second EOF reception')
    data_err = data_err[:-1]

    # return normal and error output
    return data, data_err

  def exec_raw_no_follow(self, command):
    if isinstance(command, bytes):
      command_bytes = command
    else:
      command_bytes = bytes(command, encoding='utf8')

    # check we have a prompt
    data = self.read_until(1, b'>')
    if not data.endswith(b'>'):
      raise CpBoardError('could not enter raw repl')

    # write command
    chunk_size = self._options.chunk_size
    for i in range(0, len(command_bytes), chunk_size):
      self.serial.write(command_bytes[i:min(i + chunk_size, len(command_bytes))])
      time.sleep(self._options.chunk_wait)
    self.serial.write(b'\x04')

    # check if we could exec command
    data = self.serial.read(2)
    if data != b'OK':
      raise CpBoardError(f'could not exec command, {data=}')

  def exec_raw(self, command, timeout=10, data_consumer=None):
    self.exec_raw_no_follow(command);
    return self.follow(timeout, data_consumer)

  def eval(self, expression):
    ret = self.exec('print({})'.format(expression))
    ret = ret.strip()
    return ret

  def exec(self, command):
    ret, ret_err = self.exec_raw(command)
    if ret_err:
      raise CpBoardError('exception', ret, ret_err)
    return ret

  def execfile(self, filename):
    with open(filename, 'rb') as f:
      pyfile = f.read()
    return self.exec(pyfile)

  def get_time(self):
    t = str(self.eval('cpb.RTC().datetime()'), encoding='utf8')[1:-1].split(', ')
    return int(t[4]) * 3600 + int(t[5]) * 60 + int(t[6])

def execfile(filename, port='/dev/ttyACM0',baudrate=115200):
  cpb = CpBoard(port, baudrate)
  cpb.enter_raw_repl()
  output = cpb.execfile(filename)
  stdout_write_bytes(output)
  cpb.exit_raw_repl()
  cpb.close()

def execbuffer(buf,args):
  try:
    cpb = CpBoard(args.port, args.baudrate, args.wait)
    cpb.enter_raw_repl()
    ret, ret_err = cpb.exec_raw(buf,
                                timeout=None, data_consumer=stdout_write_bytes)
    cpb.exit_raw_repl()
    cpb.close()
  except CpBoardError as er:
    print(er)
    sys.exit(1)
  except KeyboardInterrupt:
    sys.exit(1)
  if ret_err:
    stdout_write_bytes(ret_err)
    sys.exit(1)

def main():
  import argparse
  cmd_parser = argparse.ArgumentParser(description='Run scripts on the board.')
  cmd_parser.add_argument(
    '--port',
    default='/dev/ttyACM0',
    help='the serial device of the board')
  cmd_parser.add_argument(
    '-b', '--baudrate',
    default=115200,
    help='the baud rate of the serial device')
  cmd_parser.add_argument(
    '-c', '--command',
    help='program passed in as string')
  cmd_parser.add_argument(
    '-w', '--wait',
    default=0, type=int,
    help='seconds to wait for USB connected board to become available')
  cmd_parser.add_argument(
    '--follow',
    action='store_true',
    help='follow the output after running the scripts [default if no scripts given]')
  cmd_parser.add_argument('files', nargs='*', help='input files')
  args = cmd_parser.parse_args()

  if args.command is not None:
    execbuffer(args.command.encode('utf-8'))

  for filename in args.files:
    with open(filename, 'rb') as f:
      pyfile = f.read()
      execbuffer(pyfile)

  if args.follow or (args.command is None and len(args.files) == 0):
    try:
      cpb = CpBoard(args.port, args.baudrate, args.wait)
      ret, ret_err = cpb.follow(timeout=None, data_consumer=stdout_write_bytes)
      cpb.close()
    except CpBoardError as er:
      print(er)
      sys.exit(1)
    except KeyboardInterrupt:
      sys.exit(1)
    if ret_err:
      stdout_write_bytes(ret_err)
      sys.exit(1)

if __name__ == "__main__":
  main()
