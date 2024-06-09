# -------------------------------------------------------------------------
# This is a port of rshell (https://github.com/dhylands/rshell) to CircuitPython.
#
# This file maps the locale of the Circuitpython-version to the locale-specific
# message of "soft reboot". N.B: the locale must match what is running on
# the device, not the locale of the host.
#
# Author: Bernhard Bablok
# License: MIT
#
# Website: https://github.com/bablokb/cp-shell
# -------------------------------------------------------------------------

CP_LOCALE = {
  "ID": b'memulai ulang software(soft reboot)\r\n',
  "de": b'weicher reboot\r\n',
  "es": b'reinicio suave\r\n',
  "fil": b'malambot na reboot\r\n',
  "fr": 'redémarrage logiciel\r\n'.encode('utf-8'),
  "ja": 'ソフトリブート\r\n'.encode('utf-8'),
  "nl": b'zachte herstart\r\n',
  "pl": b'programowy reset\r\n',
  "pt": 'reinicialização soft\r\n'.encode('utf-8'),
  "ru": 'Мягкая перезагрузка\r\n'.encode('utf-8'),
  "sv": b'mjuk omstart\r\n',
  "zh_Latn_pinyin": 'ruǎn chóngqǐ\r\n'.encode('utf-8'),
  }
