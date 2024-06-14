# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implementation of class CmdShell. Individual commands are delegated to
# command-classes.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

import cmd
import sys
import os
import shutil
import shlex
import itertools
import traceback

from . import utils
from . import device
from .commands.command import Command

# --- readline and workaround   ----------------------------------------------

# Under OSX, if you call input with a prompt which contains ANSI escape
# sequences for colors, and readline is installed, then the escape sequences
# do not get rendered properly as colors.
#
# One solution would be to not use readline, but then you'd lose TAB completion.
# So I opted to print the colored prompt before calling input, which makes
# things work most of the time. If you try to backspace when at the first
# column of the input it wipes out the prompt, but everything returns to normal
# if you hit return.

import readline
import rlcompleter
if readline.__doc__ and 'libedit' in readline.__doc__:
  readline.parse_and_bind ("bind ^I rl_complete")
else:
  readline.parse_and_bind("tab: complete")

# DELIMS is used by readline for determining word boundaries.
DELIMS = ' \t\n>;'

# --- Helper class for file-write operation   --------------------------------

class SmartFile(object):
  """Class which implements a write method which can takes bytes or str."""

  def __init__(self, file):
    self.file = file

  def close(self):
    self.file.close()

  def flush(self):
    self.file.flush()

  def read(self, num_bytes):
    return self.file.buffer.read(num_bytes)

  def seek(self, pos):
    self.file.seek(pos)

  def tell(self):
    return self.file.tell()

  def write(self, data):
    if isinstance(data, str):
      return self.file.write(data)
    return self.file.buffer.write(data)

# --- Helper class for errors   ----------------------------------------------

class CmdShellError(Exception):
  """Errors that we want to report to the user and keep running."""
  pass

# --- Main commandline interpreter   ------------------------------------------

class CmdShell(cmd.Cmd):
  """Implements the shell as a command line interpreter."""

  def __init__(self, options, **kwargs):
    cmd.Cmd.__init__(self, **kwargs)
    self._options = options
    if 'stdin' in kwargs:
      cmd.Cmd.use_rawinput = 0

    self.real_stdout = self.stdout
    self.smart_stdout = SmartFile(self.stdout)

    self.stderr = SmartFile(sys.stderr)

    self.filename = options.filename
    self.line_num = 0
    self.timing = options.timing

    self.cur_dir = os.getcwd()
    self.prev_dir = self.cur_dir
    self.columns = shutil.get_terminal_size().columns

    self.redirect_dev = None
    self.redirect_filename = ''
    self.redirect_mode = ''

    self.quit_when_no_output = False
    self.quit_serial_reader = False
    readline.set_completer_delims(DELIMS)

    self.set_prompt()

  def print(self,*args, end='\n', file=None):
    """Convenience function so you don't need to remember to put the \n
    at the end of the line.
    """
    if file is None:
      file = self.stdout
    s = ' '.join(str(arg) for arg in args) + end
    file.write(s)

  def set_prompt(self):
    if self.stdin == sys.stdin:
      prompt = self._options.prompt_color + self.cur_dir + self._options.end_color + '> '
      if self._options.fake_input_prompt:
        print(prompt, end='')
        self.prompt = ''
      else:
        self.prompt = prompt
    else:
      # Executing commands from a file
      self.prompt = ''

  def emptyline(self):
    """We want empty lines to do nothing. By default they would repeat the
    previous command.

    """
    pass

  def _escape(self,str):
    """Precede all special characters with a backslash."""
    out = ''
    for char in str:
      if char in '\\ ':
        out += '\\'
      out += char
    return out

  def _unescape(self,str):
    """Undoes the effects of the escape() function."""
    out = ''
    prev_backslash = False
    for char in str:
      if not prev_backslash and char == '\\':
        prev_backslash = True
        continue
      out += char
      prev_backslash = False
    return out

  def filename_complete(self, text, line, begidx, endidx):
    """Wrapper for catching exceptions since cmd seems to silently
      absorb them.
    """
    try:
      return self.real_filename_complete(text, line, begidx, endidx)
    except:
      self._options.debug and traceback.print_exc()

  def real_filename_complete(self, text, line, begidx, endidx):
    """Figure out what filenames match the completion."""

    # line contains the full command line that's been entered so far.
    # text contains the portion of the line that readline is trying to complete
    # text should correspond to line[begidx:endidx]
    #
    # The way the completer works text will start after one of the characters
    # in DELIMS. So if the filename entered so far was "embedded\ sp" then
    # text will point to the s in sp.
    #
    # The following bit of logic backs up to find the real beginning of the
    # filename.

    if begidx >= len(line):
      # This happens when you hit TAB on an empty filename
      before_match = begidx
    else:
      for before_match in range(begidx, 0, -1):
        if line[before_match] in DELIMS and before_match >= 1 and line[before_match - 1] != '\\':
          break

    # We set fixed to be the portion of the filename which is before text
    # and match is the full portion of the filename that's been entered so
    # far (that's the part we use for matching files).
    #
    # When we return a list of completions, the bit that we return should
    # just be the portion that we replace 'text' with.

    fixed = self._unescape(line[before_match+1:begidx]) # fixed portion of the match
    match = self._unescape(line[before_match+1:endidx]) # portion to match filenames against

    # We do the following to cover the case that the current directory
    # is / and the path being entered is relative.
    strip = ''
    if len(match) > 0 and match[0] == '/':
      abs_match = match
    elif self.cur_dir == '/':
      abs_match = self.cur_dir + match
      strip = self.cur_dir
    else:
      abs_match = self.cur_dir + '/' + match
      strip = self.cur_dir + '/'

    completions = []
    prepend = ''
    dev = device.Device.get_device()
    if dev and abs_match.rfind('/') == 0:  # match is in the root directory
      # This means that we're looking for matches in the root directory
      # (i.e. abs_match is /foo and the user hit TAB).
      # So we'll supply the matching board names as possible completions.
      # Since they're all treated as directories we leave the trailing slash.
      if dev.name_path.startswith(abs_match):
        if match[0] == '/':
          completions.append(dev.name_path)
        else:
          completions.append(dev.name_path[1:])
      # Add root directories of the default device (i.e. /flash/ and /sd/)
      if match[0] == '/':
        completions += [
          root_dir for root_dir in dev.root_dirs if root_dir.startswith(match)]
      else:
        completions += [
          root_dir[1:] for root_dir in dev.root_dirs
                                             if root_dir[1:].startswith(match)]
    elif dev:
      # This means that there are at least 2 slashes in abs_match. If one
      # of them matches a board name then we need to remove the board
      # name from fixed. Since the results from listdir_matches won't
      # contain the board name, we need to prepend each of the completions.
      if abs_match.startswith(dev.name_path):
        prepend = dev.name_path[:-1]

    paths = sorted(utils.auto(listdir_matches, abs_match))
    for path in paths:
      path = prepend + path
      if path.startswith(strip):
        path = path[len(strip):]
      completions.append(self._escape(path.replace(fixed, '', 1)))
    return completions

  def directory_complete(self, text, line, begidx, endidx):
    """Figure out what directories match the completion."""
    return [filename for filename in self.filename_complete(text, line, begidx, endidx) if filename[-1] == '/']

  # --- parse line, handling redirection   -----------------------------------

  def line_to_args(self, line):
    """ parse line and handle redirection """

    # Note: using shlex.split causes quoted substrings to stay together.
    try:
      args = shlex.split(line)
    except ValueError as err:
      raise device.DeviceError(str(err))
    self.redirect_filename = ''
    self.redirect_dev = None
    redirect_index = -1
    if '>' in args:
      redirect_index = args.index('>')
    elif '>>' in args:
      redirect_index = args.index('>>')
    if redirect_index >= 0:
      if redirect_index + 1 >= len(args):
        raise CmdShellError("> requires a filename")
      self.redirect_filename = utils.resolve_path(
        args[redirect_index + 1],self.cur_dir)
      rmode = utils.auto(utils.get_mode, os.path.dirname(self.redirect_filename))
      if not utils.mode_isdir(rmode):
        raise CmdShellError("Unable to redirect to '%s', directory doesn't exist" %
                         self.redirect_filename)
      if args[redirect_index] == '>':
        self.redirect_mode = 'w'
        if self._options.debug:
          print('Redirecting (write) to', self.redirect_filename)
      else:
        self.redirect_mode = 'a'
        if self._options.debug:
          print('Redirecting (append) to', self.redirect_filename)
      self.redirect_dev, self.redirect_filename = (
        utils.get_dev_and_path(self.redirect_filename))
      try:
        if self.redirect_dev is None:
          self.stdout = SmartFile(open(self.redirect_filename, self.redirect_mode))
        else:
          # Redirecting to a remote device. We collect the results locally
          # and copy them to the remote device at the end of the command.
          self.stdout = SmartFile(tempfile.TemporaryFile(mode='w+'))
      except OSError as err:
        raise CmdShellError(err)

      del args[redirect_index + 1]
      del args[redirect_index]
    return args

  # --- overrides of super-class methods for command-processing   ------------

  def precmd(self, line):
    self.stdout = self.smart_stdout
    return line

  def onecmd(self, line):
    """Override onecmd.

    1 - So we don't have to have a do_EOF method.
    2 - So we can strip comments
    3 - So we can track line numbers
    """
    if self._options.debug:
      print('Executing "%s"' % line)
    self.line_num += 1
    if line == "EOF" or line == 'exit':
      if cmd.Cmd.use_rawinput:
        # This means that we printed a prompt, and we'll want to
        # print a newline to pretty things up for the caller.
        self.print('')
      return True
    # Strip comments
    comment_idx = line.find("#")
    if comment_idx >= 0:
      line = line[0:comment_idx]
      line = line.strip()

    # search multiple commands on the same line
    lexer = shlex.shlex(line)
    lexer.whitespace = ''

    for issemicolon, group in itertools.groupby(lexer, lambda x: x == ";"):
      if not issemicolon:
        self.onecmd_exec("".join(group))

  def postcmd(self, stop, line):
    if self.stdout != self.smart_stdout:
      if self.redirect_dev is not None:
        # Redirecting to a remote device, now that we're finished the
        # command, we can copy the collected output to the remote.
        if self._options.debug:
          print('Copy redirected output to "%s"' % self.redirect_filename)
        # This belongs on the remote. Copy/append now
        filesize = self.stdout.tell()
        self.stdout.seek(0)
        self.redirect_dev.remote(recv_file_from_host, self.stdout,
                                 self.redirect_filename, filesize,
                                 dst_mode=self.redirect_mode,
                                 xfer_func=send_file_to_remote)
      self.stdout.close()
    self.stdout = self.real_stdout
    if not stop:
      self.set_prompt()
    return stop

  # --- execute a single command, i.e. delegate to super-class onecmd   ------

  def onecmd_exec(self, line):
    try:
      if self.timing:
        start_time = time.time()
        result = cmd.Cmd.onecmd(self, line)
        end_time = time.time()
        print('took %.3f seconds' % (end_time - start_time))
        return result
      else:
        return cmd.Cmd.onecmd(self, line)
    except SystemExit:
      # When you use -h with argparse it winds up call sys.exit, which
      # raises a SystemExit. We intercept it because we don't want to
      # exit the shell, just the command.
      return False
    except Exception as err:
      utils.print_err(err)
      self._options.debug and traceback.print_exc()

  # --- delegate do_help to our standard multiplexer   -----------------------

  def do_help(self,line):
    self.default(line)

  # --- multiplex commands, i.e. call run() of command-subclass   ------------

  def default(self, line):
    """
    We don't use cmdCmd do_* logic, because this code is more generic:
    we can add new commands just by adding new classes to the module
    """

    cmd, _, _ = self.parseline(self.lastcmd)
    args = self.line_to_args(line)
    try:
      cmdinstance = Command.create(cmd,self)
    except:
      self._options.debug and print(traceback.print_exc())
      utils.print_err("Unrecognized command:",line)
      return

    if self._options.debug:
      print(f"DEBUG: default(): {line=}")
      print(f"DEBUG: default(): {cmd=}")
      print(f"DEBUG: default(): {args=}")
      print(f"DEBUG: default(): cmdinstance: {cmdinstance}")

    cmdinstance.run(args)

  # --- main command-loop   --------------------------------------------------

  def cmdloop(self, line=None):
    if line:
      line = self.precmd(line)
      stop = self.onecmd(line)
      stop = self.postcmd(stop, line)
    else:
      cmd.Cmd.cmdloop(self)
