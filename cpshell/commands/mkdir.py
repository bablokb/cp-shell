# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'mkdir' command.
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

def make_directory(dirname):
  """Creates one or more directories."""
  import os
  try:
    os.mkdir(dirname)
  except:
    return False
  return True

def mkdir(filename):
  """Creates a directory."""
  return utils.auto(make_directory, filename)

class Mkdir(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"mkdir")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """mkdir DIRECTORY...

      Creates one or more directories.
    """
    for filename in args:
      filename = utils.resolve_path(filename,self.shell.cur_dir)
      if not mkdir(filename):
        utils.print_err('Unable to create %s' % filename)
