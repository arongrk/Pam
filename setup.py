from distutils.core import setup
import py2exe
import os

# includes = ['scipy.special.cython_special']
# sys.path.append('C:\\Users\\dasa\\PycharmProjects\\MatlabData\\venv\\Lib\\site-packages\\PyQt5\\Qt5\\plugins\\platforms\\qwindows.dll')
# include = [r'C:\Users\dasa\PycharmProjects\MatlabData\venv\Lib\site-packages\PyQt5\Qt5\plugins\platforms\qwindows.dll']
# data_file = [("platforms", ["C:C:\\Users\\dasa\\PycharmProjects\\MatlabData\\venv\\Lib\\site-packages\\PyQt5\\Qt\\plugins\\platforms\\qwindows.dll"])]

files = []
for file in os.listdir('c:/users/dasa/pycharmprojects/matlabdata/resources'):
    f1 = 'C:/Users/dasa/PycharmProjects/MatlabData/resources/' + file
    if os.path.isfile(f1): # skip directories
        files.append(f1)
setup(
    windows=['pam.py'],
    data_files=[('resources', files)]
)
