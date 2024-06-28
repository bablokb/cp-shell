# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'rsync' command.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

import time
import os

from cpshell import utils
from cpshell import device
from cpshell.options import Options

from .command import Command 
from .mkdir import mkdir
from .rm import rm

# --- shared low-level implementation of commands   --------------------------

def rsync(src_dir, dst_dir, mirror, dry_run, print_func, recursed, sync_hidden):
  """Synchronizes 2 directory trees."""
  # This test is a hack to avoid errors when accessing /flash. When the
  # cache synchronisation issue is solved it should be removed
  if not isinstance(src_dir, str) or not len(src_dir):
    return
  
  from .cp import cp # do it here to prevent circular imports

  if '__pycache__' in src_dir:       # ignore __pycache__
    return

  time_offset = -time.localtime().tm_gmtoff
  sstat = utils.auto(utils.get_stat, src_dir, time_offset)
  smode = utils.stat_mode(sstat)
  if utils.mode_isfile(smode):
    utils.print_err('Source {} is a file not a directory.'.format(src_dir))
    return

  d_src = {}  # Look up stat tuple from name in current directory
  src_files = utils.auto(utils.listdir_stat,src_dir,
                         time_offset,show_hidden=sync_hidden)
  if src_files is None:
    utils.print_err('Source directory {} does not exist.'.format(src_dir))
    return
  for name, stat in src_files:
    if '__pycache__' in name:       # ignore __pycache__
      continue
    d_src[name] = stat

  d_dst = {}
  dst_files = utils.auto(utils.listdir_stat,dst_dir,
                         time_offset,show_hidden=sync_hidden)
  if dst_files is None: # Directory does not exist
    if not make_dir(dst_dir, dry_run, print_func, recursed):
      return
  else: # dest exists
    for name, stat in dst_files:
      d_dst[name] = stat

  set_dst = set(d_dst.keys())
  set_src = set(d_src.keys())
  to_add = set_src - set_dst  # Files to copy to dest
  to_del = set_dst - set_src  # To delete from dest
  to_upd = set_dst.intersection(set_src) # In both: may need updating

  for src_basename in to_add:  # Name in source but absent from destination
    src_filename = src_dir + '/' + src_basename
    dst_filename = dst_dir + '/' + src_basename
    if dry_run or Options.get().debug:
      print_func("Adding %s" % dst_filename)
    src_stat = d_src[src_basename]
    src_mode = utils.stat_mode(src_stat)
    if not dry_run:
      if not utils.mode_isdir(src_mode):
        cp(src_filename, dst_filename)
    if utils.mode_isdir(src_mode):
      rsync(src_filename, dst_filename, mirror=mirror, dry_run=dry_run,
            print_func=print_func, recursed=True, sync_hidden=sync_hidden)

  if mirror:  # May delete
    for dst_basename in to_del:  # In dest but not in source
      dst_filename = dst_dir + '/' + dst_basename
      if dry_run or Options.get().debug:
        print_func("Removing %s" % dst_filename)
      if not dry_run:
        rm(dst_filename, recursive=True, force=True)

  for src_basename in to_upd:  # Names are identical
    src_stat = d_src[src_basename]
    dst_stat = d_dst[src_basename]
    src_filename = src_dir + '/' + src_basename
    dst_filename = dst_dir + '/' + src_basename
    src_mode = utils.stat_mode(src_stat)
    dst_mode = utils.stat_mode(dst_stat)
    if utils.mode_isdir(src_mode):
      if utils.mode_isdir(dst_mode):
        # src and dst are both directories - recurse
        rsync(src_filename, dst_filename, mirror=mirror, dry_run=dry_run,
              print_func=print_func, recursed=True, sync_hidden=sync_hidden)
      else:
        msg = "Source '{}' is a directory and destination " \
              "'{}' is a file. Ignoring"
        utils.print_err(msg.format(src_filename, dst_filename))
    else:
      if utils.mode_isdir(dst_mode):
        msg = "Source '{}' is a file and destination " \
              "'{}' is a directory. Ignoring"
        utils.print_err(msg.format(src_filename, dst_filename))
      else:
        if Options.get().debug:
          print_func('Checking {}'.format(dst_filename))

        mtime_src = utils.stat_mtime(src_stat)
        mtime_dst = utils.stat_mtime(dst_stat)
        if Options.get().debug:
          print_func(f"DEBUG: mtime(src)={utils.mtime_pretty(mtime_src)}")
          print_func(f"DEBUG: mtime(dst)={utils.mtime_pretty(mtime_dst)}")
        if mtime_src > mtime_dst:
          if dry_run or Options.get().debug:
            print_func(f"{src_filename} is newer than {dst_filename} - copying")
          if not dry_run:
            cp(src_filename, dst_filename)

def make_dir(dst_dir, dry_run, print_func, recursed):
  """Creates a directory. Produces information in case of dry run.
  Issues error where necessary.
  """
  parent = os.path.split(dst_dir.rstrip('/'))[0] # Check for nonexistent parent
  parent_files = utils.auto(utils.listdir_lstat,parent,0) if parent else True # Relative dir
  if dry_run:
    if recursed: # Assume success: parent not actually created yet
      print_func(f"Creating directory {dst_dir}")
    elif parent_files is None:
      print_func(f"Unable to create {dst_dir}")
    return True

  Options.get().verbose and print(f"mkdir {dst_dir}")
  if not mkdir(dst_dir):
    utils.print_err(f"Unable to create {dst_dir}")
    return False
  return True

# --- Command-class for rsync   ----------------------------------------------

class Rsync(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"rsync")

  # --- add arguments to parser   --------------------------------------------

  def add_args(self):
    """ Add arguments to parser. """

    self.parser.add_argument(
      '-a', '--all',
      dest='all',
      action='store_true',
      help='Don\'t ignore files starting with .',
      default=False
    )
    self.parser.add_argument(
      '-m', '--mirror',
      dest='mirror',
      action='store_true',
      help="causes files in the destination which don't exist in "
               "the source to be removed. Without --mirror only file "
               "copies occur. No deletions will take place.",
      default=False,
    )
    self.parser.add_argument(
        '-n', '--dry-run',
        dest='dry_run',
        action='store_true',
        help='shows what would be done without actually performing '
        'any file copies. Implies --verbose.',
        default=False
    )
    self.parser.add_argument(
        '-q', '--quiet',
        dest='quiet',
        action='store_true',
        help='Doesn\'t show what has been done.',
        default=False
    )
    self.parser.add_argument(
        'src_dir',
        metavar='SRC_DIR',
        help='Source directory'
    )
    self.parser.add_argument(
        'dst_dir',
        metavar='DEST_DIR',
        help='Destination directory'
    )

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """rsync [-m|--mirror] [-n|--dry-run] [-q|--quiet] SRC_DIR DEST_DIR

      Synchronizes a destination directory tree with a source directory tree.
    """

    args = self.parser.parse_args(args)
    src_dir = utils.resolve_path(args.src_dir,self.shell.cur_dir)
    dst_dir = utils.resolve_path(args.dst_dir,self.shell.cur_dir)
    verbose = not args.quiet
    pf = print if args.dry_run or verbose else lambda *args : None
    rsync(src_dir, dst_dir, mirror=args.mirror, dry_run=args.dry_run,
         print_func=pf, recursed=False, sync_hidden=args.all)
