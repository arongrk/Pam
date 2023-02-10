from ctypes import c_int32

MARKER = c_int32(0xaaffffff).value
MARKER_BYTES = b'\xaa\xff\xff\xff'
PACKAGE_LENGTH = 350
PLOT_LENGTH = 40960
