# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'cat' command.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

from .command import Command 
from cpshell.options import Options
from cpshell import utils
from cpshell import device

def cat(src_filename, dst_file):
  """Copies the contents of the indicated file to an already opened file."""
  (dev, dev_filename) = utils.get_dev_and_path(src_filename)
  if dev is None:
    with open(dev_filename, 'rb') as txtfile:
      for line in txtfile:
        dst_file.write(line)
  else:
    filesize = dev.remote_eval(utils.get_filesize, dev_filename)
    return dev.remote(utils.send_file_to_host, dev_filename, dst_file,
                      filesize, Options.get().buffer_size,
                      xfer_func=utils.recv_file_from_remote)

class Cat(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"cat")

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """cat FILENAME...

      Concatenates files and sends to stdout.
    """
    # note: when we get around to supporting cat from stdin, we'll need
    #       to write stdin to a temp file, and then copy the file
    #       since we need to know the filesize when copying to the board.

    for filename in args:
      filename = utils.resolve_path(filename,self.shell.cur_dir)
      mode = utils.auto(utils.get_mode, filename)
      if not utils.mode_exists(mode):
        utils.print_err("Cannot access '%s': No such file" % filename)
        continue
      if not utils.mode_isfile(mode):
        utils.print_err("'%s': is not a file" % filename)
        continue
      cat(filename, self.shell.stdout)
