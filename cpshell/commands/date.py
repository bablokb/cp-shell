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

import sys
import time
from datetime import datetime

from .command import Command 
from cpshell import utils
from cpshell import device

# --- helper functions   -----------------------------------------------------

def date():
  import time
  return time.time()

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
      time_offset = -time.localtime().tm_gmtoff
      dt = datetime.fromtimestamp(dev.remote_eval(date)+time_offset)
    else:
      dt = datetime.now()
    self.shell.print(f'{dt.strftime("%c")}')
