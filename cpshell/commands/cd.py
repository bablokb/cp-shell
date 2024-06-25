# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'cd' command.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

from .command import Command 
from cpshell import utils
from cpshell import device

def chdir(dirname):
  """Changes the current working directory."""
  import os
  os.chdir(dirname)

class Cd(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"cd")

  # --- special completer   --------------------------------------------------

  def complete(self,text,line,begidx,endidx):
    """ special completer for directories. Overrides Command.complete() """
    return self.shell.directory_complete(text, line, begidx, endidx)

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """cd DIRECTORY

      Changes the current directory. ~ expansion is supported, and cd -
      goes to the previous directory.
    """

    if len(args) == 0:
      dirname = '~'
    else:
      if args[0] == '-':
        dirname = self.shell.prev_dir
      else:
        dirname = args[0]
    dirname = utils.resolve_path(dirname,self.shell.cur_dir)

    mode = utils.auto(utils.get_mode, dirname)
    if utils.mode_isdir(mode):
      self.shell.prev_dir = self.shell.cur_dir
      self.shell.cur_dir = dirname
      utils.auto(chdir, dirname)
    else:
      utils.print_err("Directory '%s' does not exist" % dirname)
