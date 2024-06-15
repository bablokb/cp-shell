# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'help' command.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

from cpshell import commands
from cpshell import utils
from cpshell import device

class Help(commands.command.Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"help")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    help [COMMAND]

      List available commands with no arguments, or detailed help when
      a command is provided.
    """
    if not args:
      # print help for help (i.e. ourselves)
      self.parser.print_help()

      import pkgutil
      all_cmds = [mod.name for mod in list(
                                       pkgutil.iter_modules(commands.__path__))]
      self.shell.print("="*20)
      self.shell.print("Available commands:")
      for cmd in all_cmds:
        if cmd != "command":
          self.shell.print(f"  {cmd}")
      self.shell.print("="*20)
      return

    # create command and parser and print help of command
    try:
      cmd = commands.command.Command.create(args[0],self.shell)
      cmd.parser.print_help()
    except:
      utils.print_err(f"no help for {args[0]} - unknown command?!")
