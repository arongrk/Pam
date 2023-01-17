from threading import Thread
import bokeh
import numpy as np
from multiprocessing import shared_memory
import random as rnd

import matlabdata

start_data = matlabdata.load_ABC()
shm = shared_memory.SharedMemory(name='storage', create=True, size=start_data.nbytes)

