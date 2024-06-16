# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'shell' command.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

import os

from .command import Command 
from cpshell import utils
from cpshell import device

class Shell(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"shell")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    !some-shell-command args

    Launches a shell and executes whatever command you provide. If you
    don't provide any commands, then it will launch a bash sub-shell
    and when exit from bash (Control-D) then it will return to cpshell.
    """
    if not args:
      args = ['/bin/bash']
    #TODO: check if can call subprocess instead - args should be already
    #      run through shelex
    os.system(" ".join(args))
