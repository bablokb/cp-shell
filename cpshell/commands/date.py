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

from .command import Command 
from cpshell import utils
from cpshell import device

# --- helper functions   -----------------------------------------------------

def date():
  import time
  tm = time.localtime()
  dow = ('Mon', 'Tue', 'Web', 'Thu', 'Fri', 'Sat', 'Sun')
  mon = ('???', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
  return repr('{} {} {:2d} {:02d}:{:02d}:{:02d} {}'.format(dow[tm[6]], mon[tm[1]], tm[2], tm[3], tm[4], tm[5], tm[0]))

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
      self.shell.print(f'{dev.name}: {dev.remote_eval(date)}')
    else:
      self.shell.print('Host:', eval(date()))
