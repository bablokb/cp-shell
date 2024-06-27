# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Utility functions.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

import os
import sys
import time
import inspect
import fnmatch
import binascii

from .options import Options

if sys.platform == 'win32':
  EXIT_STR = 'Use the exit command to exit cpshell.'
else:
  EXIT_STR = 'Use Control-D (or the exit command) to exit cpshell.'

from . import device

def extra_funcs(*funcs):
  """Decorator which adds extra functions to be downloaded to the board."""
  def extra_funcs_decorator(real_func):
    def wrapper(*args, **kwargs):
      return real_func(*args, **kwargs)
    wrapper.extra_funcs = list(funcs)
    wrapper.source = inspect.getsource(real_func)
    wrapper.name = real_func.__name__
    return wrapper
  return extra_funcs_decorator

def print_err(*args, end='\n'):
  """Similar to print, but prints to stderr.
  """
  print(*args, end=end, file=sys.stderr)
  sys.stderr.flush()

def resolve_path(path,cur_dir):
  """Resolves path and converts it into an absolute path."""
  if path[0] == ':':
    return path if len(path)>1 else ":/" 
  if path[0] == '~':
    # ~ or ~user
    path = os.path.expanduser(path)
  if path[0] != '/':
    # Relative path
    if cur_dir[-1] == '/':
      path = cur_dir + path
    else:
      path = cur_dir + '/' + path
  comps = path.split('/')
  new_comps = []
  for comp in comps:
    # We strip out xxx/./xxx and xxx//xxx, except that we want to keep the
    # leading / for absolute paths. This also removes the trailing slash
    # that autocompletion adds to a directory.
    if comp == '.' or (comp == '' and len(new_comps) > 0):
      continue
    if comp == '..':
      if len(new_comps) > 1:
        new_comps.pop()
    else:
      new_comps.append(comp)
  if len(new_comps) == 1 and new_comps[0] == '':
    return '/'
  return '/'.join(new_comps)

def validate_pattern(fn,cur_dir):
  """On success return an absolute path and a pattern.
  Otherwise print a message and return None, None
  """
  directory, pattern = parse_pattern(fn)
  if directory is None:
    print_err("Invalid pattern {}.".format(fn))
    return None, None
  target = resolve_path(directory,cur_dir)
  mode = auto(get_mode, target)
  if not mode_exists(mode):
    print_err("cannot access '{}': No such file or directory".format(fn))
    return None, None
  if not mode_isdir(mode):
    print_err("cannot access '{}': Not a directory".format(fn))
    return None, None
  return target, pattern

def process_pattern(fn,cur_dir):
  """Return a list of paths matching a pattern (or None on error).
  """
  directory, pattern = validate_pattern(fn,cur_dir)
  if directory is not None:
    filenames = fnmatch.filter(auto(listdir, directory), pattern)
    if filenames:
      return [directory + '/' + sfn for sfn in filenames]
    else:
      print_err("cannot access '{}': No such file or directory".format(fn))

def auto(func, filename, *args, **kwargs):
  """If `filename` is a remote file, then this function calls func on the
    CircuitPython board, otherwise it calls it locally.
  """
  dev, dev_filename = get_dev_and_path(filename)
  if dev is None:
    if len(dev_filename) > 0 and dev_filename[0] == '~':
      dev_filename = os.path.expanduser(dev_filename)
    return func(dev_filename, *args, **kwargs)
  return dev.remote_eval(func, dev_filename, *args, **kwargs)

def get_dev_and_path(filename):
  """Determines if a given file is located locally or remotely. We assume
    that any directories from the board take precedence over local
    directories of the same name. /flash and /sdcard are associated with
    the default device. /dev_name/path where dev_name is the name of a
    given device is also considered to be associated with the named device.

    If the file is associated with a remote device, then this function
    returns a tuple (dev, dev_filename) where dev is the device and
    dev_filename is the portion of the filename relative to the device.

    If the file is not associated with the remote device, then the dev
    portion of the returned tuple will be None.
  """
  dev = device.Device.get_device()
  if filename[0] == ':':
    return (dev, filename[1:])
  if dev:
    if dev.is_root_path(filename):
      return (dev, filename)
    test_filename = filename + '/'
    if test_filename.startswith(dev.name_path):
      dev_filename = filename[len(dev.name_path)-1:]
      if dev_filename == '':
        dev_filename = '/'
      return (dev, dev_filename)
  return (None, filename)

def get_mode(filename):
  """Returns the mode of a file, which can be used to determine if a file
    exists, if a file is a file or a directory.
  """
  import os
  try:
    # Since this function runs remotely, it can't depend on other functions,
    # so we can't call stat_mode.
    return os.stat(filename)[0]
  except OSError:
    return 0


def lstat(filename,time_offset):
  """Returns os.lstat for a given file, adjusting the timestamps as appropriate.
    This function will not follow symlinks."""
  import os
  try:
    # on the host, lstat won't try to follow symlinks
    rstat = os.lstat(filename)
    return rstat
  except:
    rstat = os.stat(filename)
    print("")
    return rstat[:7] + tuple(tim + time_offset for tim in rstat[7:])


def stat(filename,time_offset):
  """Returns os.stat for a given file, adjusting the timestamps as appropriate."""
  import os
  rstat = os.stat(filename)
  if hasattr(os,'lstat'):
    return rstat
  else:
    return rstat[:7] + tuple(tim + time_offset for tim in rstat[7:])


def mode_exists(mode):
  return mode & 0xc000 != 0

def mode_isdir(mode):
  return mode & 0x4000 != 0

def mode_issymlink(mode):
  return mode & 0xf000 == 0xa000

def mode_isfile(mode):
  return mode & 0x8000 != 0

def stat_mode(stat):
  """Returns the mode field from the results returned by os.stat()."""
  return stat[0]

def stat_size(stat):
  """Returns the filesize field from the results returned by os.stat()."""
  return stat[6]

def stat_mtime(stat):
  """Returns the mtime field from the results returned by os.stat()."""
  return stat[8]

def sysname():
  """Returns the os.uname().sysname field."""
  try:
    import os
    return repr(os.uname().sysname)
  except:
    return repr('unknown')


def is_visible(filename):
  """Determines if the file should be considered to be a non-hidden file."""
  return filename[0] != '.' and filename[-1] != '~'


@extra_funcs(stat)
def get_stat(filename,time_offset):
  """Returns the stat array for a given file. Returns all 0's if the file
    doesn't exist.
  """
  try:
    return stat(filename,time_offset)
  except OSError:
    return (0,) * 10


@extra_funcs(lstat)
def get_lstat(filename,time_offset):
  """Returns the stat array for a given file. Returns all 0's if the file
    doesn't exist.
  """
  try:
    return lstat(filename,time_offset)
  except OSError:
    return (0,) * 10


def listdir(dirname):
  """Returns a list of filenames contained in the named directory."""
  import os
  return os.listdir(dirname)


def listdir_matches(match):
  """Returns a list of filenames contained in the named directory.
    Only filenames which start with `match` will be returned.
    Directories will have a trailing slash.
  """
  import os
  last_slash = match.rfind('/')
  if last_slash == -1:
    dirname = '.'
    match_prefix = match
    result_prefix = ''
  else:
    match_prefix = match[last_slash + 1:]
    if last_slash == 0:
      dirname = '/'
      result_prefix = '/'
    else:
      dirname = match[0:last_slash]
      result_prefix = dirname + '/'
  def add_suffix_if_dir(filename):
    try:
      if (os.stat(filename)[0] & 0x4000) != 0:
        return filename + '/'
    except FileNotFoundError:
      # This can happen when a symlink points to a non-existant file.
      pass
    return filename
  matches = [add_suffix_if_dir(result_prefix + filename)
             for filename in os.listdir(dirname) if filename.startswith(match_prefix)]
  return matches


@extra_funcs(is_visible, lstat)
def listdir_lstat(dirname, time_offset,show_hidden=True):
  """Returns a list of tuples for each file contained in the named
    directory, or None if the directory does not exist. Each tuple
    contains the filename, followed by the tuple returned by
    calling os.stat on the filename.
  """
  import os
  try:
    files = os.listdir(dirname)
  except OSError:
    return None
  if dirname == '/':
    return list((file, lstat('/' + file,time_offset)) for file in files if is_visible(file) or show_hidden)
  return list((file, lstat(dirname + '/' + file,time_offset)) for file in files if is_visible(file) or show_hidden)


@extra_funcs(is_visible, stat)
def listdir_stat(dirname, time_offset, show_hidden=True):
  """Returns a list of tuples for each file contained in the named
    directory, or None if the directory does not exist. Each tuple
    contains the filename, followed by the tuple returned by
    calling os.stat on the filename.
  """
  import os
  try:
    files = os.listdir(dirname)
  except OSError:
    return None
  if dirname == '/':
    return list((file, stat('/' + file,time_offset)) for file in files if is_visible(file) or show_hidden)
  return list((file, stat(dirname + '/' + file,time_offset)) for file in files if is_visible(file) or show_hidden)


# rtc_time[0] - year    4 digit
# rtc_time[1] - month   1..12
# rtc_time[2] - day     1..31
# rtc_time[3] - hour    0..23
# rtc_time[4] - minute  0..59
# rtc_time[5] - second  0..59
# rtc_time[6] - weekday 1..7 1=Sunday
# rtc_time[7] - yearday 1..366 or -1
# rtc_time[8] - isdst   0, 1, or -1
def set_time(rtc_time):
  import rtc
  import time    
  rtc.RTC().datetime = time.struct_time(rtc_time)

def decorated_filename(filename, stat):
  """Takes a filename and the stat info and returns the decorated filename.
    The decoration takes the form of a single character which follows
    the filename. Currently, the only decoration is '/' for directories.
  """
  mode = stat[0]
  if mode_isdir(mode):
    return Options.get().dir_color + filename + Options.get().end_color + '/'
  if mode_issymlink(mode):
    return filename + '@'
  if filename.endswith('.py'):
    return Options.get().py_color + filename + Options.get().end_color
  return filename


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

# 0x0D's sent from the host get transformed into 0x0A's, and 0x0A sent to the
# host get converted into 0x0D0A when using sys.stdin. sys.tsin.buffer does
# no transformations, so if that's available, we use it, otherwise we need
# to use hexlify in order to get unaltered data.

def recv_file_from_host(src_file, dst_filename, filesize, buf_size,dst_mode='wb'):
  """Function which runs on the board. Matches up with send_file_to_remote."""
  import sys
  import binascii
  import os
  try:
    import time
    with open(dst_filename, dst_mode) as dst_file:
      bytes_remaining = filesize
      bytes_remaining *= 2  # hexlify makes each byte into 2
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

    buf_size = Options.get().buffer_size // 2
    read_size = min(bytes_remaining, buf_size)
    buf = src_file.read(read_size)
    #sys.stdout.write('\r%d/%d' % (filesize - bytes_remaining, filesize))
    #sys.stdout.flush()
    dev.write(binascii.hexlify(buf))
    bytes_remaining -= read_size
  #sys.stdout.write('\r')
  dev.timeout = save_timeout


def recv_file_from_remote(dev, src_filename, dst_file, filesize, buf_size):
  """Intended to be passed to the `remote` function as the xfer_func argument.
    Matches up with send_file_to_host.
  """
  bytes_remaining = filesize
  bytes_remaining *= 2  # hexlify makes each byte into 2
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


def send_file_to_host(src_filename, dst_file, filesize, buf_size):
  """Function which runs on the board. Matches up with recv_file_from_remote."""
  import sys
  import binascii
  try:
    with open(src_filename, 'rb') as src_file:
      bytes_remaining = filesize
      buf_size = buf_size // 2
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

def connect(port, baud=115200, wait=0):
  """Connect to a CircuitPython board via a serial port."""
  options = Options.get()
  options.debug and print(
    'Connecting to %s (buffer-size %d)...' % (port,options.buffer_size))
  try:
    dev = device.DeviceSerial(options,port, baud, wait)
    device.Device.set_device(dev)
    options.verbose and print(f"connected to {dev.port}")
  except device.DeviceError as err:
    sys.stderr.write(str(err))
    sys.stderr.write('\n')
    return False
  return True

