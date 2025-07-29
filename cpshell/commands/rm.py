# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'rm' command.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

from cpshell import utils
from cpshell import device
from cpshell.options import Options

from .command import Command 

# --- shared low-level implementation of commands   --------------------------

def remove_file(filename, recursive=False, force=False):
  """Removes a file or directory."""
  import os
  try:
    mode = os.stat(filename)[0]
    if mode & 0x4000 != 0:
      # directory
      if recursive:
        for file in os.listdir(filename):
          success = remove_file(filename + '/' + file, recursive, force)
          if not success and not force:
            return False
        os.rmdir(filename) # PGH Work like Unix: require recursive
      else:
        if not force:
          return False
    else:
      os.remove(filename)
  except:
    if not force:
      return False
  return True


def rm(filename, recursive=False, force=False):
  """Removes a file or directory tree."""
  if recursive:
    utils.print_verbose(f"rm -r {filename}")
  else:
    utils.print_verbose(f"rm {filename}")
  return utils.auto(remove_file, filename, recursive, force)


# --- Command-class for rm   -------------------------------------------------

class Rm(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"rm")

  # --- add arguments to parser   --------------------------------------------

  def add_args(self):
    """ Add arguments to parser. """

    self.parser.add_argument(
        '-r', '--recursive',
        dest='recursive',
        action='store_true',
        help='remove directories and their contents recursively',
        default=False
    )
    self.parser.add_argument(
        '-f', '--force',
        dest='force',
        action='store_true',
        help='ignore nonexistent files and arguments',
        default=False
    )
    self.parser.add_argument(
        'filename',
        metavar='FILE',
        nargs='+',
        help='Pattern or files and directories to remove'
    )

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    rm [-f|--force] FILE...            Remove one or more files
    rm [-f|--force] PATTERN            Remove multiple files
    rm -r [-f|--force] [FILE|DIRECTORY]... Files and/or directories
    rm -r [-f|--force] PATTERN         Multiple files and/or directories

    Removes files or directories. To remove directories (and
    any contents) -r must be specified.
    """

    args = self.parser.parse_args(args)
    filenames = args.filename
    # Process PATTERN
    sfn = filenames[0]
    if utils.is_pattern(sfn):
      if len(filenames) > 1:
        utils.print_err("Usage: rm [-r] [-f] PATTERN")
        return
      filenames = utils.process_pattern(sfn,self.shell.cur_dir)
      if filenames is None:
        return

    for filename in filenames:
      filename = utils.resolve_path(filename,self.shell.cur_dir)
      if not rm(filename, recursive=args.recursive, force=args.force):
        if not args.force:
          utils.print_err("Unable to remove '{}'".format(filename))
        break
