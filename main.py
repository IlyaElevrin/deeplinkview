# main.py
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from main_window import LinksViewer

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    font = QFont()
    font.setFamily("Arial")
    font.setPointSize(10)
    app.setFont(font)

    viewer = LinksViewer()
    viewer.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()