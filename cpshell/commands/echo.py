# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'echo' command.
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

class Echo(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"echo")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    echo TEXT...

    Display a line of text.
    """
    self.shell.print(*args)
