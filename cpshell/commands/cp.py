# ----------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# Implement 'cp' command.
#
# Author: Bernhard Bablok
# Original Author: Dave Hylands
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# ----------------------------------------------------------------------------

import os
import time

from cpshell.options import Options
from cpshell import utils
from cpshell import device

from .command import Command
from .filesize import get_filesize
from .mkdir import mkdir

def copy_file(src_filename, dst_filename, buf_size):
  """Copies a file from one place to another. Both the source and destination
    files must exist on the same machine.
  """
  try:
    with open(src_filename, 'rb') as src_file:
      with open(dst_filename, 'wb') as dst_file:
        while True:
          buf = src_file.read(buf_size)
          if len(buf) > 0:
            dst_file.write(buf)
          if len(buf) < buf_size:
            break
    return True
  except:
    return False

def cp(src_filename, dst_filename):
  """Copies one file to another. The source file may be local or remote and
    the destination file may be local or remote.
  """
  src_dev, src_dev_filename = utils.get_dev_and_path(src_filename)
  dst_dev, dst_dev_filename = utils.get_dev_and_path(dst_filename)

  Options.get().verbose and print(f"cp {src_filename} {dst_filename}")
  if src_dev is dst_dev:
    # src and dst are either on the same remote, or both are on the host
    return utils.auto(copy_file, src_filename,
                      dst_dev_filename,
                      Options.get().buffer_size)

  filesize = utils.auto(get_filesize, src_filename)

  if dst_dev is None:
    # Copying from remote to host
    with open(dst_dev_filename, 'wb') as dst_file:
      return src_dev.remote(utils.send_file_to_host,
                            src_dev_filename, dst_file,
                            filesize, Options.get().buffer_size,
                            xfer_func=utils.recv_file_from_remote)
  if src_dev is None:
    # Copying from host to remote
    with open(src_dev_filename, 'rb') as src_file:
      return dst_dev.remote(utils.recv_file_from_host,
                            src_file, dst_dev_filename,
                            filesize, Options.get().buffer_size,
                            xfer_func=utils.send_file_to_remote)


class Cp(Command):

  # --- constructor   --------------------------------------------------------

  def __init__(self,shell):
    """ constructor """
    super().__init__(shell,"cp")

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
        '-r', '--recursive',
        dest='recursive',
        action='store_true',
        help='Copy directories recursively',
        default=False
    )
    self.parser.add_argument(
        'filenames',
        metavar='FILE',
        nargs='+',
        help='Pattern or files and directories to copy'
    )

  # --- run command   --------------------------------------------------------

  def run(self,args):
    """
    cp SOURCE DEST               Copy a single SOURCE file to DEST file.
    cp SOURCE... DIRECTORY       Copy multiple SOURCE files to a directory.
    cp [-r|--recursive] [SOURCE|SOURCE_DIR]... DIRECTORY
    cp [-r] PATTERN DIRECTORY    Copy matching files to DIRECTORY.

    The destination must be a directory except in the case of
    copying a single file. To copy directories -r must be specified.
    This will cause directories and their contents to be recursively
    copied.
    """

    time_offset = -time.localtime().tm_gmtoff
    args = self.parser.parse_args(args)
    src_filenames = args.filenames[:-1]

    if len(args.filenames) < 2:
      utils.print_err('Missing destination file')
      return
    dst_dirname = utils.resolve_path(args.filenames[-1],self.shell.cur_dir)

    dst_mode = utils.auto(utils.get_mode, dst_dirname)
    d_dst = {}  # Destination directory: lookup stat by basename
    if args.recursive:
      dst_files = utils.auto(utils.listdir_stat,dst_dirname,time_offset)
      if dst_files is None:
        if utils.is_pattern(src_filenames[0]):
          utils.print_err(f"target {dst_dirname} is not a directory")
          return
        if not mkdir(dst_dirname):
          utils.print_err(f"Unable to create directory {dst_dirname}")
          return
        dst_mode = utils.auto(utils.get_mode, dst_dirname)
        src_filenames[0] += '/*'
      else:
        for name, stat in dst_files:
          d_dst[name] = stat

    # Process PATTERN
    sfn = src_filenames[0]
    if utils.is_pattern(sfn):
      if len(src_filenames) > 1:
        utils.print_err("Usage: cp [-r] PATTERN DIRECTORY")
        return
      src_filenames = utils.process_pattern(sfn,self.shell.cur_dir)
      if src_filenames is None:
        return

    for src_filename in src_filenames:
      if utils.is_pattern(src_filename):
        utils.print_err("Only one pattern permitted.")
        return
      src_filename = utils.resolve_path(src_filename,self.shell.cur_dir)
      if '__pycache__' in src_filename:              # don't copy __pycache__
        continue
      src_mode = utils.auto(utils.get_mode, src_filename)
      if not utils.mode_exists(src_mode):
        utils.print_err("File '{}' doesn't exist".format(src_filename))
        return
      if utils.mode_isdir(src_mode):
        if args.recursive: # Copying a directory
          src_basename = os.path.basename(src_filename)
          dst_filename = dst_dirname + '/' + src_basename
          if src_basename in d_dst:
            dst_stat = d_dst[src_basename]
            dst_mode = utils.stat_mode(dst_stat)
            if not utils.mode_isdir(dst_mode):
              err = "Destination {} is not a directory"
              utils.print_err(err.format(dst_filename))
              return
          else:
            if not mkdir(dst_filename):
              err = "Unable to create directory {}"
              utils.print_err(err.format(dst_filename))
              return

          from .rsync import rsync # do it here to prevent circular imports!
          rsync(src_filename, dst_filename, mirror=False, dry_run=False,
                print_func=lambda *args: None, recursed=False, sync_hidden=args.all)
        else:
          utils.print_err("Omitting directory {}".format(src_filename))
        continue
      if utils.mode_isdir(dst_mode):
        dst_filename = dst_dirname + '/' + os.path.basename(src_filename)
      else:
        dst_filename = dst_dirname
      if not cp(src_filename, dst_filename):
        err = "Unable to copy '{}' to '{}'"
        utils.print_err(err.format(src_filename, dst_filename))
        break
