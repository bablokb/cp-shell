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

import time
import fnmatch

from .command import Command 
from cpshell import utils
from cpshell import device

# --- helper functions   -----------------------------------------------------

SIX_MONTHS = 183 * 24 * 60 * 60
MONTH = ('', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
         'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

def print_long(filename, stat, print_func):
  """Prints detailed information about the file passed in."""
  size = utils.stat_size(stat)
  mtime = utils.stat_mtime(stat)
  file_mtime = time.localtime(mtime)
  curr_time = time.time()
  if mtime > (curr_time + SIX_MONTHS) or mtime < (curr_time - SIX_MONTHS):
    print_func('%6d %s %2d %04d  %s' % (size, MONTH[file_mtime[1]],
                                        file_mtime[2], file_mtime[0],
                                        utils.decorated_filename(filename, stat)))
  else:
    print_func('%6d %s %2d %02d:%02d %s' % (
      size, MONTH[file_mtime[1]],
      file_mtime[2], file_mtime[3], file_mtime[4],
      utils.decorated_filename(filename, stat)))

def word_len(word):
  """Returns the word length, minus any color codes."""
  if word[0] == '\x1b':
    return len(word) - 11   # 7 for color, 4 for no-color
  return len(word)

def print_cols(words, print_func, termwidth=79):
  """Takes a single column of words, and prints it as multiple columns that
  will fit in termwidth columns.
  """
  width = max([word_len(word) for word in words])
  nwords = len(words)
  ncols = max(1, (termwidth + 1) // (width + 1))
  nrows = (nwords + ncols - 1) // ncols
  for row in range(nrows):
    for i in range(row, nwords, nrows):
      word = words[i]
      if word[0] == '\x1b':
        print_func('%-*s' % (width + 11, words[i]),
                   end='\n' if i + nrows >= nwords else ' ')
      else:
        print_func('%-*s' % (width, words[i]),
                   end='\n' if i + nrows >= nwords else ' ')


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
    time_offset = -time.localtime().tm_gmtoff
    if len(args.filenames) == 0:
      args.filenames = ['.']
    for idx, fn in enumerate(args.filenames):
      if not utils.is_pattern(fn):
        filename = utils.resolve_path(fn,self.shell.cur_dir)
        stat = utils.auto(utils.get_stat, filename, time_offset)
        mode = utils.stat_mode(stat)
        if not utils.mode_exists(mode):
          utils.print_err(
            f"Cannot access '{filename}': No such file or directory")
          continue
        if not utils.mode_isdir(mode):
          if args.long:
            print_long(fn, stat, self.shell.print)
          else:
            self.shell.print(fn)
          continue
        if len(args.filenames) > 1:
          if idx > 0:
            self.shell.print('')
          self.shell.print(f"{filename}:")
        pattern = '*'
      else: # A pattern was specified
        filename, pattern = validate_pattern(fn,self.shell.cur_dir)
        if filename is None: # An error was printed
          continue
      files = []
      ldir_stat = utils.auto(utils.listdir_lstat, filename, time_offset)
      if ldir_stat is None:
        utils.print_err(
          f"Cannot access '{filename}': No such file or directory")
      else:
        for filename, stat in sorted(ldir_stat,
                                     key=lambda entry: entry[0]):
          if utils.is_visible(filename) or args.all:
            if fnmatch.fnmatch(filename, pattern):
              if args.long:
                print_long(filename, stat, self.shell.print)
              else:
                files.append(utils.decorated_filename(filename, stat))
      if len(files) > 0:
        print_cols(sorted(files), self.shell.print, self.shell.columns)
