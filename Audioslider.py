import sys
import numpy as np
import time

import pyaudio
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic
from PyQt5.QtGui import QIcon, QPixmap
from pyaudio import PyAudio, paFloat32
from pyqtgraph import mkPen
import sounddevice as sd


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        if True:
            with open('resources/pams_style.qss', 'r') as f:
                self.setStyleSheet(f.read())
            uic.loadUi('resources/audio_slider.ui', self)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.maximize_button.clicked.connect(self.maximize_button_clicked)
            self.med_ic = QIcon('resources/medimize_button.svg')
            self.med_ic_white = QIcon('resources/medimize_button_white.svg')
            self.max_ic = QIcon('resources/maximize_button.svg')
            self.max_ic_white = QIcon('resources/maximize_button_white.svg')
            self.min_ic = QIcon('resources/minimize_button.svg')
            self.min_ic_white = QIcon('resources/minimize_button_white.svg')
            self.clos_ic = QIcon('resources/closing_button.svg')
            self.clos_ic_white = QIcon('resources/closing_button_white.svg')
            self.maximize_button.enterEvent = self.maximize_button_hover
            self.maximize_button.leaveEvent = self.maximize_button_exit
            self.minimize_button.enterEvent = self.minimize_button_hover
            self.minimize_button.leaveEvent = self.minimize_button_exit
            self.close_button.enterEvent = self.close_button_hover
            self.close_button.leaveEvent = self.close_button_exit
        # self.pyaudio = PyAudio()

        self.SAMPLE_DURATION = 1000
        self.SAMPLE_RATE = 44100
        self.FREQUENCY = self.freq_slider.value()
        self.VOLUME = self.volume_slider.value() / 100

        plot_sine_wave = True
        if plot_sine_wave:
            freq = self.FREQUENCY
            vol = self.VOLUME
            wave = np.sin(np.arange(int(self.SAMPLE_RATE/freq))/self.SAMPLE_RATE*np.pi*2*freq)*vol
            pen = mkPen(color=(0, 0, 0), width=1)
            self.line = self.sine_plot.plot(np.arange(10), pen=pen)
            self.sine_plot.setBackground('w')
            # self.sine_plot.disableAutoRange()
            # self.sine_plot.setYRange(-1, 1)
            # self.sine_plot.setXRange(0, self.SAMPLE_RATE/100)

        # SineAudioEmitter class setup
        if True:
            self.sinSender = SineAudioEmitter(self.SAMPLE_RATE, 10, plot_sine_wave=True, plot_mode='')
            self.start_button.clicked.connect(self.sinSender.start)
            self.stop_button.clicked.connect(self.sinSender.stop)
            # self.sinSender.sin_ready.connect(self.change_plot)
            self.freq_slider.valueChanged.connect(self.sinSender.set_frequency)
            self.volume_slider.valueChanged.connect(self.sinSender.set_volume)
            self.sinSender.sin_ready.connect(self.change_plot)

        if True: # Device choose setup
            # print(self.sinSender.p.get_device_info_by_index(1))
            for i in range(self.sinSender.p.get_device_count()):
                device_info = self.sinSender.p.get_device_info_by_index(i)
                if device_info['maxOutputChannels'] > 0:
                    self.devices_box.addItem(str(device_info['name'].encode('latin-1').decode('utf-8')))
            current_device_info = self.sinSender.p.get_default_output_device_info()
            print(current_device_info)
            self.devices_box.setCurrentText(current_device_info['name'].encode('latin-1').decode('utf-8'))
            self.display_device_info(current_device_info)
            self.change_dev_button.clicked.connect(self.refresh_current_device)

    def display_device_info(self, device_info):
        d_inf = device_info
        self.name_label.setText(str(d_inf['name'].encode('latin-1').decode('utf-8')))
        self.index_label.setText(str(d_inf['index']))
        self.channels_label.setText(str(d_inf['maxOutputChannels']))
        self.samprate_label.setText(str(int(d_inf['defaultSampleRate'])))

    def refresh_current_device(self):
        self.sinSender.stop()
        self.sinSender.DEVICE = 1

    def change_plot(self, data: tuple):
        self.line.setData(data[1], data[0])

    def close_button_hover(self, event):
        self.close_button.setIcon(self.clos_ic_white)

    def close_button_exit(self, event):
        self.close_button.setIcon(self.clos_ic)

    def maximize_button_hover(self, event):
        if self.isFullScreen():
            self.maximize_button.setIcon(self.med_ic_white)
        else:
            self.maximize_button.setIcon(self.max_ic_white)

    def maximize_button_exit(self, event):
        if self.isFullScreen():
            self.maximize_button.setIcon(self.med_ic)
        else:
            self.maximize_button.setIcon(self.max_ic)

    def minimize_button_hover(self, event):
        self.minimize_button.setIcon(self.min_ic_white)

    def minimize_button_exit(self, event):
        self.minimize_button.setIcon(self.min_ic)

    def maximize_button_clicked(self):
        if self.isFullScreen():
            self.showNormal()
            self.maximize_button.setIcon(self.max_ic)
        else:
            self.maximize_button.setIcon(self.med_ic)
            self.showFullScreen()

    def close(self):
        self.sinSender.stop()
        self.sinSender.wait()
        super().close()


class SineAudioEmitter(QThread):
    sin_ready = pyqtSignal(tuple)

    def __init__(self, sample_rate: int = 44100, refresh_rate: int = 1, frequency: int = 440,
                 volume: int = 50, device_index=None, plot_sine_wave: bool = False, plot_mode: str = 'all'):
        QThread.__init__(self)
        self.DEVICE = device_index
        self.SAMPLE_RATE = sample_rate
        self.frequency = frequency
        self.volume = volume / 100
        self.num_samp = int(sample_rate * refresh_rate / 1000)

        self.stop_sender = False
        self.p = pyaudio.PyAudio()

        self.plot_sin = plot_sine_wave
        self.plot_mode = 0 if plot_mode == 'all' else 1

    def set_frequency(self, frequency):
        self.frequency = frequency

    def set_volume(self, volume):
        self.volume = volume / 100

    def run(self):
        self.stop_sender = False
        stream = self.p.open(rate=self.SAMPLE_RATE,
                             format=paFloat32,
                             channels=1,
                             output=True,
                             output_device_index=self.DEVICE,
                             frames_per_buffer=0)
        pi2 = np.pi*2
        npfloat32 = np.float32

        samprate = self.SAMPLE_RATE
        num_samp = self.num_samp
        volume = self.volume
        frequency = self.frequency

        values = np.arange(1, num_samp+1, dtype=npfloat32)/samprate*pi2*frequency
        volume_array = np.linspace(0, volume, num_samp, dtype=npfloat32)
        sinewave = np.sin(values, dtype=npfloat32) * volume_array

        stream.write(sinewave, num_frames=num_samp)
        self.sin_ready.emit((sinewave, np.arange(num_samp)))

        do_plot = 0

        while not self.stop_sender:
            # Set up the volume array and sweep in case the volume changed
            if volume == self.volume:
                volume_array = np.array([volume]*num_samp, dtype=npfloat32)
            else:
                volume_array = np.linspace(volume, self.volume, num_samp, dtype=npfloat32)
                do_plot += 1
            volume = self.volume

            # Set up the frequency values and a sweep in case the frequency changed
            if frequency == self.frequency:
                values = np.arange(1, num_samp+1, dtype=npfloat32)/samprate*pi2*frequency + (values[-1] % pi2)
            elif self.frequency == 0:
                print('0')
                volume_array = np.linspace(volume, 0, num_samp, dtype=npfloat32)
                values = pi2 * np.cumsum(np.linspace(frequency, self.frequency, num_samp)) / samprate+(values[-1] % pi2)
                do_plot += 1
            else:
                values = pi2 * np.cumsum(np.linspace(frequency, self.frequency, num_samp)) / samprate+(values[-1] % pi2)
                do_plot += 1
            frequency = self.frequency

            # Writing the sine wave
            sinewave = np.sin(values, dtype=npfloat32) * volume_array
            stream.write(sinewave, num_frames=num_samp)
            if self.plot_sin:
                if self.plot_mode == 0:
                    self.sin_ready.emit((sinewave, np.arange(num_samp)))
                else:
                    if do_plot > 0:
                        self.sin_ready.emit((sinewave, np.arange(num_samp)))
                        do_plot = 0
        values = np.arange(1, num_samp+1, dtype=npfloat32)/samprate*pi2*self.frequency + (values[-1] % pi2)
        sinewave = np.sin(values, dtype=npfloat32) * np.linspace(volume, 0, num_samp, dtype=npfloat32)
        stream.write(sinewave, num_frames=num_samp)
        self.sin_ready.emit((sinewave, np.arange(num_samp)))
        zeros = np.zeros(num_samp, dtype=npfloat32)
        for i in range(10):
            stream.write(zeros, num_frames=num_samp)
        stream.close()

    def stop(self):
        self.stop_sender = True


def main():
    app = QApplication(sys.argv)
    pixmap = QPixmap('resources/splash_screen.png')
    splashscreen = QSplashScreen(pixmap)
    splashscreen.show()
    window = MainWindow()
    window.show()
    splashscreen.finish(window)
    app.exec()


if __name__ == '__main__':
    main()
    '''


import sys
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QBuffer, QIODevice, QByteArray, QDataStream, QThread, QObject
from PyQt5.QtMultimedia import QAudioDeviceInfo, QAudioFormat, QAudioOutput, QAudio
from PyQt5.QtWidgets import QApplication, QMainWindow, QSlider, QVBoxLayout, QWidget, QPushButton
import pyqtgraph
import time
import sounddevice
import rtmixer
import pyaudio

from pams_functions import unconnect


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Player")

        # Create sliders for frequency and volume
        self.freq_slider = QSlider(Qt.Orientation.Horizontal)
        self.freq_slider.setMinimum(30)
        self.freq_slider.setMaximum(1000)
        self.freq_slider.setValue(60)
        self.freq_slider.valueChanged.connect(self.update_tone)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.update_tone)

        self.start_button = QPushButton('start')
        self.start_button.clicked.connect(self.start_output)
        self.stop_button = QPushButton('stop')
        self.stop_button.clicked.connect(self.stop_output)

        # Create layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.freq_slider)
        self.layout.addWidget(self.volume_slider)
        self.layout.addWidget(self.start_button)
        self.layout.addWidget(self.stop_button)

        # Create widget and set layout
        self.centralWidget = QWidget()
        self.centralWidget.setLayout(self.layout)
        self.setCentralWidget(self.centralWidget)
        self.timer = QTimer()

        self.SAMPLE_RATE = 44100
        self.SAMPLE_DURATION = 1 / self.SAMPLE_RATE
        self.SOUND_REFRESH_RATE = 1
        self.SAMPLE_SIZE = int(self.SAMPLE_RATE * self.SOUND_REFRESH_RATE)
        self.FREQUENCY = 600
        self.VOLUME = 0.5
        self.end_value = self.SOUND_REFRESH_RATE
        self.time_stamps = np.arange(0, self.end_value, self.SAMPLE_DURATION, dtype=np.float32)
        self.signal = (np.sin(self.time_stamps * np.pi * 2 * self.FREQUENCY) * self.VOLUME)
        self.start_value = 0
        sounddevice.default.channels = 1
        sounddevice.default.samplerate = self.SAMPLE_RATE
        sounddevice.default.latency = 'low'
        self.p = pyaudio.PyAudio()
        # self.audio_stream = sounddevice.OutputStream(samplerate=self.SAMPLE_RATE, latency='low', dtype='float32')
        print('sounddevice defaults:\n'
              f'    Device: {sounddevice.default.device}\n'
              f'    Sample Rate: {sounddevice.default.samplerate}\n'
              f'    Channels: {sounddevice.default.channels}\n'
              f'    Block Size: {sounddevice.default.blocksize}\n'
              f'    Latency: {sounddevice.default.latency}\n\n'
              
              'Values:\n'
              f'    Sample Rate: {self.SAMPLE_RATE}\n'
              f'    Sound refresh rate: {self.SOUND_REFRESH_RATE}\n'
              f'    Sample Size: {self.SAMPLE_SIZE}\n'
              f'    Frequency: {self.FREQUENCY}\n'
              f'    Sample duration{self.SAMPLE_DURATION:.15f}')

        self.CREATE_PLOT = True
        if self.CREATE_PLOT:
            self.plot_widget = pyqtgraph.PlotWidget()
            self.layout.addWidget(self.plot_widget)

        self.t0 = 0
        self.playback = Playback(self.SAMPLE_RATE)

    def start_output(self):
        # self.audio_stream.start()
        self.timer.start(int(self.SOUND_REFRESH_RATE*1000))
        self.timer.timeout.connect(self.output_signal)
        self.playback.start()
        # self.output_signal()

    def stop_output(self):
        unconnect(self.timer.timeout, self.output_signal)
        # self.audio_stream.stop(ignore_errors=True)

    def update_tone(self):
        self.VOLUME = self.volume_slider.value() / 100
        self.FREQUENCY = self.freq_slider.value() * 10

    def output_signal(self):
        self.t0 = time.time()
        self.start_value = self.end_value
        self.end_value += self.SOUND_REFRESH_RATE
        self.time_stamps = np.arange(self.start_value, self.end_value, self.SAMPLE_DURATION)
        self.playback.signal = (np.sin(self.time_stamps * np.pi * 2 * self.FREQUENCY, dtype=np.float32))
        # self.plot_widget.plot(self.time_stamps, signal)
        # self.audio_stream.write(signal)
        # print(f'first value: {signal[0]}, last value: {signal[-1]},'
        #       f' start_value: {self.start_value}, end_value: {self.end_value}'
        #       f' array length: {len(signal)}')


class Playback(QObject):
    def __init__(self, samplerate, latency='low'):
        super().__init__()
        self.signal = np.zeros(1000, dtype=np.float32)
        self.samplerate = samplerate
        self.latency = latency

    def start(self):
        stream = sounddevice.OutputStream(samplerate=self.samplerate, latency=self.latency, dtype='float32')
        stream.start()
        playsound = True
        while playsound:
            print('trying')
            signal = self.signal
            stream.write(signal)
        stream.stop()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
'''