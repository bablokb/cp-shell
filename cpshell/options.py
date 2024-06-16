# -------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implementation of class Options. This hold a global options-object
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# -------------------------------------------------------------------------

class Options:
  options = None

  # --- return options-object (create if not already cached)   ------------

  @classmethod
  def get(cls):
    """ return the options-instance, create if necessary  """
    if not Options.options:
      Options.options = Options()
    return Options.options
