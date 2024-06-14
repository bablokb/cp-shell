# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'date' command.
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

class Date(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"date")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    Displays the current date and time for the connected board.
    """

    dev = device.Device.get_device()
    if dev:
      self.shell.print('{}: {}'.format(
        dev.name, utils.trim(dev.remote_eval(utils.date))))
    else:
      self.shell.print('Host:', eval(utils.date()))
