import sys
from PyQt5.QtWidgets import QApplication
from UI import CellposeApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CellposeApp()
    window.show()
    sys.exit(app.exec_())



