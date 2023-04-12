from distutils.core import setup
import py2exe
import os

# includes = ['scipy.special.cython_special']
# sys.path.append('C:\\Users\\dasa\\PycharmProjects\\MatlabData\\venv\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\platforms\\qwindows.dll')
# include = [r'C:\Users\dasa\PycharmProjects\MatlabData\venv\Lib\site-packages\PyQt5\Qt5\plugins\platforms\qwindows.dll']
# data_file = [("platforms", ["C:C:\\Users\\dasa\\PycharmProjects\\MatlabData\\venv\\Lib\\site-packages\\PyQt5\\Qt\\plugins\\platforms\\qwindows.dll"])]

files = []
for files in os.listdir('C:Users/dasa/PycharmProjects/MatlabData/resources'):
    f1 = 'C:Users/dasa/PycharmProjects/MatlabData/resources' + files
    if os.path.isfile(f1): # skip directories
        f2 = 'images', [f1]
        files.append(f2)
setup(
    windows=['pam.py']
    # data_files = data_file
)
