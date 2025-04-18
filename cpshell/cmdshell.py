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

    if self._options.debug:
      print(f"\nDEBUG: {text=}")
      print(f"DEBUG: {line=}")
      print(f"DEBUG: {begidx=}")
      print(f"DEBUG: {endidx=}")

    dev = device.Device.get_device()

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

    if self._options.debug:
      print(f"DEBUG: {fixed=}")
      print(f"DEBUG: {match=}")

    # without a connected device we cannot match remote filenames
    if match and match[0] == ':':
      if not dev:
        return []
      else:
        dev_match = True
        match = match[1:]
    else:
      dev_match = False

    if match:
      if match == '/':       # input is top-level root directory
        abs_match = '/'
        match_dir = '/'
      elif match[0] == '/':   # input is absolute
        abs_match = match
        match_dir = abs_match.rstrip('/') + '/'
      elif self.cur_dir in ['/',':/']:
        abs_match = self.cur_dir + match
        match_dir = self.cur_dir
      else:
        abs_match = self.cur_dir + '/' + match
        match_dir = self.cur_dir + '/'
    else:
      abs_match = self.cur_dir + '/'
      match_dir = self.cur_dir + '/'

    abs_match = abs_match.rstrip(':')
    match_dir = match_dir.rstrip(':')
    if self._options.debug:
      print(f"DEBUG: {abs_match=}")
      print(f"DEBUG: {match_dir=}\n")

    completions = []
    prepend = ''
    if dev_match and not abs_match.rfind('/'):
      # match in the root-directory of the device
        return [
          root_dir for root_dir in dev.root_dirs if root_dir.startswith(match)]
    elif dev_match:
      # match in a subdirectory of the device
      prepend = ':'

    paths = sorted(utils.auto(utils.listdir_matches, abs_match))
    for path in paths:
      if path.startswith(match_dir):
        path = path[len(match_dir):]
      path = prepend + path
      completions.append(self._escape(path.replace(fixed, '', 1)))
    return completions

  def directory_complete(self, text, line, begidx, endidx):
    """Figure out what directories match the completion."""
    return [filename for filename in
            self.filename_complete(text, line, begidx, endidx)
            if filename and filename[-1] == '/']

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
    # hide escaped semicolon from lexer
    line = line.replace('\;','\x00')
    lexer = shlex.shlex(line)
    lexer.whitespace = ''

    for issemicolon, group in itertools.groupby(lexer, lambda x: x == ";"):
      if not issemicolon:
        # resurrect hidden semicolon if necessary
        single_cmd = "".join(group).replace('\x00',';')
        self.onecmd_exec(single_cmd)

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
        self.redirect_dev.remote(utils.recv_file_from_host, self.stdout,
                                 self.redirect_filename,
                                 filesize, self._options.buffer_size,
                                 dst_mode=self.redirect_mode,
                                 xfer_func=utils.send_file_to_remote)
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

  # --- list of command-names   ----------------------------------------------

  def completenames(self, text, *ignored):
    """
    Since we don't use the do_* logic, we override matching command-names.
    """

    commands = Command.all_commands()
    return [c for c in commands if c.startswith(text)]

  # --- our own completer   --------------------------------------------------

  def completedefault(self,text, line, begidx, endidx):
    """
    Since we don't use the do_* logic, we need our own completer for
    commands and arguments.
    """

    cmd, _, _ = self.parseline(line)
    try:
      cmdinstance = Command.create(cmd,self)
      return cmdinstance.complete(text,line,begidx,endidx)
    except:
      self._options.debug and print(traceback.print_exc())
      utils.print_err("Unrecognized command:",line)
      raise

# --- delegate do_help to our standard multiplexer   -----------------------

  def do_help(self,line):
    self.default("help "+line)

  # --- delegate do_shell to our standard multiplexer   ----------------------

  def do_shell(self, line):
    self.default("shell "+line)

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

    cmdinstance.run(args[1:])

  # --- main command-loop   --------------------------------------------------

  def cmdloop(self, line=None):
    if line:
      line = self.precmd(line)
      stop = self.onecmd(line)
      stop = self.postcmd(stop, line)
    else:
      cmd.Cmd.cmdloop(self)
