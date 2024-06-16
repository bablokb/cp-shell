# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'exit' command. This class is not used except for providing help.
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

class Exit(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"exit")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    exit

    Exits from cpshell.
    """
    return True
