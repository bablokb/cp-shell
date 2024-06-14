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

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell,name):
    """ constructor """
    self.shell  = shell
    self._name  = name
    self._create_argparser()

  # --- create argparser from comments within run()   ------------------------

  def _create_argparser(self):
    doc_lines = getattr(self, "run").__doc__.expandtabs().splitlines()
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

  # --- run command   --------------------------------------------------------

  def run(self,line):
    """ Run command. Must be implemented by subclass """
    pass
