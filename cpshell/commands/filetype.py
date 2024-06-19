# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'filetype' command.
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

class Filetype(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"filetype")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    filetype FILE

    Prints the type of file (dir or file). This function is primarily
    for testing.
    """
    if len(args) == 0:
      utils.print_err("Must provide a filename")
      return
    filename = utils.resolve_path(args[0],self.shell.cur_dir)
    mode = utils.auto(utils.get_mode, filename)
    if utils.mode_exists(mode):
      if utils.mode_isdir(mode):
        self.shell.print('dir')
      elif utils.mode_isfile(mode):
        self.shell.print('file')
      else:
        self.shell.print('unknown')
    else:
      self.shell.print('missing')
