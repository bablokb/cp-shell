# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'filesize' command.
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

def get_filesize(filename):
  """Returns the size of a file, in bytes."""
  import os
  try:
    # Since this function runs remotely, it can't depend on other functions,
    # so we can't call stat_mode.
    return os.stat(filename)[6]
  except OSError:
    return -1

class Filesize(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"filesize")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    filesize FILE

    Prints the size of the file, in bytes. This function is primarily
    for testing.
    """
    if len(args) == 0:
      print_err("Must provide a filename")
      return
    filename = utils.resolve_path(args[0],self.shell.cur_dir)
    self.shell.print(utils.auto(get_filesize, filename))
