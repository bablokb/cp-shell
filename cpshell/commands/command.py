# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Base class of all shell commands.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

import argparse

class Command:

  # cache-objects
  _cmd_obj = {}
  _cmd_list = []

  # --- return command-object (create if not already cached)    --------------

  @classmethod
  def create(cls,name,shell):
    """ create an instance of the command """
    if not name in Command._cmd_obj:
      cmdmodule   = __import__(name,
                               globals(),locals(),[name.capitalize()],1)
      obj = getattr(cmdmodule,name.capitalize())(shell)
      Command._cmd_obj[name] = obj
    return Command._cmd_obj[name]

  # --- return list of all commands   ----------------------------------------

  @classmethod
  def all_commands(cls):
    """ return list of available commands """
    if not len(Command._cmd_list):
      from cpshell import commands
      import pkgutil
      Command._cmd_list = [
         mod.name for mod in
             list(pkgutil.iter_modules(commands.__path__))
                if mod.name != "command"]
    return Command._cmd_list

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell,name):
    """ constructor """
    self.shell  = shell
    self._name  = name
    self._create_argparser()

  # --- create argparser from comments within run()   ------------------------

  def _create_argparser(self):
    doc_lines = getattr(self, "run").__doc__.expandtabs().splitlines()
    if not doc_lines[0]:
      doc_lines.pop(0)
      doc_lines[0] = "\n"+doc_lines[0]
    if '' in doc_lines:
      blank_idx = doc_lines.index('')
      usage = doc_lines[:blank_idx]
      description = doc_lines[blank_idx+1:]
    else:
      usage = doc_lines
      description = []
    self.parser = argparse.ArgumentParser(
        prog=self._name,
        usage='\n'.join(usage),
        description='\n'.join(description)
    )
    self.add_args()

  # --- add arguments to parser   --------------------------------------------

  def add_args(self):
    """ Add arguments to parser. Must be implemented by subclass """
    pass

  # --- default completer   --------------------------------------------------

  def complete(self,text,line,begidx,endidx):
    """ default completer - override if necessary """
    return shell.filename_complete(text, line, begidx, endidx)

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """ Run command. Must be implemented by subclass """
    pass
