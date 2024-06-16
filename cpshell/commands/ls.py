# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'ls' command.
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

class Ls(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"ls")

  # --- add arguments to parser   --------------------------------------------

  def add_args(self):
    """ Add arguments to parser. """

    self.parser.add_argument(
      '-a', '--all',
      dest='all',
      action='store_true',
      help='do not ignore hidden files',
      default=False
    )
    self.parser.add_argument(
      '-l', '--long',
      dest='long',
      action='store_true',
      help='use a long listing format',
      default=False
    )
    self.parser.add_argument(
      'filenames',
      metavar='FILE',
      nargs='*',
      help='Files, directories or patterns to list'
    )

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    ls [-a] [-l] [FILE|DIRECTORY|PATTERN]...
    PATTERN supports * ? [seq] [!seq] Unix filename matching

    List directory contents.
    """

    args = self.parser.parse_args(args)

    if len(args.filenames) == 0:
      args.filenames = ['.']
    for idx, fn in enumerate(args.filenames):
      if not utils.is_pattern(fn):
        filename = utils.resolve_path(fn,self.shell.cur_dir)
        stat = utils.auto(utils.get_stat, filename)
        mode = utils.stat_mode(stat)
        if not utils.mode_exists(mode):
          utils.print_err(
            f"Cannot access '{filename}': No such file or directory")
          continue
        if not utils.mode_isdir(mode):
          if args.long:
            utils.print_long(fn, stat, self.shell.print)
          else:
            self.shell.print(fn)
          continue
        if len(args.filenames) > 1:
          if idx > 0:
            self.shell.print('')
          self.shell.print(f"{filename}:")
        pattern = '*'
      else: # A pattern was specified
        filename, pattern = validate_pattern(fn)
        if filename is None: # An error was printed
          continue
      files = []
      ldir_stat = utils.auto(utils.listdir_lstat, filename)
      if ldir_stat is None:
        utils.print_err(
          f"Cannot access '{filename}': No such file or directory")
      else:
        for filename, stat in sorted(ldir_stat,
                                     key=lambda entry: entry[0]):
          if utils.is_visible(filename) or args.all:
            if fnmatch.fnmatch(filename, pattern):
              if args.long:
                utils.print_long(filename, stat, self.shell.print)
              else:
                files.append(utils.decorated_filename(filename, stat))
      if len(files) > 0:
        utils.print_cols(sorted(files), self.shell.print, self.columns)
