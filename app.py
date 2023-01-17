import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("My App")
        button = QPushButton('Drück mich!')
        button.setCheckable(True)
        button.clicked.connect(self.the_button_was_clicked)
        button.clicked.connect(self.check_toggled)

        self.setCentralWidget(button)

    def the_button_was_clicked(self):
        print('clicked')

    def check_toggled(self, checked):
        print('New state: ', checked)

app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec()