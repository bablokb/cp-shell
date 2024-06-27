# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'connect' command.
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

class Connect(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"connect")

  # --- add arguments to parser   --------------------------------------------

  def add_args(self):
    """ Add arguments to parser. """

    self.parser.add_argument(
        'port',
        nargs=1,
        help='port to connect to'
    )
    self.parser.add_argument(
        'baud',
        nargs='?',
        type=int,
        default=115200,
        help='baudrate to use (defaut: 115200)'
    )

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
      connect port [baud]
      Connects a board to cpshell.
    """
    args = self.parser.parse_args(args)
    port = args.port[0]
    utils.connect(port,args.baud)
