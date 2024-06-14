# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'args' command.
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

class Args(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"args")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """args [arguments...]

      Debug function for verifying argument parsing. This function just
      prints out each argument that it receives.
    """
    for idx,arg in enumerate(args):
      self.shell.print(f"arg[{idx}] = '{arg}'")
