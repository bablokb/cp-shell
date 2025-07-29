# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'edit' command.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

import time
import tempfile
import os

from cpshell import utils
from cpshell import device
from cpshell.options import Options

from .command import Command 
from .cp import cp

class Edit(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"edit")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    edit FILE

    Copies the file locally, launches an editor to edit the file.
    When the editor exits, if the file was modified then its copied
    back.

    You can specify the editor used with the --editor command line
    option when you start cpshell, or by using the VISUAL or EDITOR
    environment variable. if none of those are set, then vi will be used.
    """

    time_offset = -time.localtime().tm_gmtoff

    if len(args) == 0:
      utils.print_err("Must provide a filename")
      return
    filename = utils.resolve_path(args[0],self.shell.cur_dir)
    dev, dev_filename = utils.get_dev_and_path(filename)
    mode = utils.auto(utils.get_mode, filename)
    if utils.mode_exists(mode) and utils.mode_isdir(mode):
      utils.print_err("Unable to edit directory '{}'".format(filename))
      return
    if dev is None:
      # File is local
      os.system("{} '{}'".format(Options.get().editor, filename))
    else:
      # File is remote
      with tempfile.TemporaryDirectory() as temp_dir:
        local_filename = os.path.join(temp_dir, os.path.basename(filename))
        if utils.mode_exists(mode):
          Options.get().verbose and self.shell.print(f"Retrieving {filename} ...")
          cp(filename, local_filename)
        old_mtime = utils.stat_mtime(utils.get_stat(local_filename,time_offset))
        if os.system("{} '{}'".format(Options.get().editor, local_filename)) == 0:
          new_mtime = utils.stat_mtime(utils.get_stat(local_filename,time_offset))
          utils.print_debug(f"DEBUG: mtime(old)={utils.mtime_pretty(old_mtime)}")
          utils.print_debug(f"DEBUG: mtime(new)={utils.mtime_pretty(new_mtime)}")
          if new_mtime > old_mtime:
            Options.get().verbose and self.shell.print(f"Updating {filename} ...")
            cp(local_filename, filename)
