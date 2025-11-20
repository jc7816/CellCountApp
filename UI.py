# UI.py — Clean version, no scale bar, no diameter input.
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QFileDialog, QMessageBox, QApplication
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import os
from worker import ProcessingThread


class CellposeApp(QMainWindow):
    """PyQt5 application for Cellpose-based segmentation with threaded worker (CPU-only)."""
    def __init__(self):
        super().__init__()

        # Window title
        self.setWindowTitle("Cell Count")
        self.setGeometry(200, 200, 1000, 700)

        # State
        self.processing_thread = None
        self.current_image = None
        self.output_folder = None
        self.is_processing = False

        # Root widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()

        # --- Preview row: input on left, result on right ---
        self.preview_row = QHBoxLayout()

        # Input image area
        self.image_label = QLabel("Drag & Drop or Click to Upload Image")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 2px dashed gray;")
        self.image_label.setFixedHeight(320)

        # Result image area
        self.result_label = QLabel("Result will appear here")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet("border: 2px dashed gray; color: gray; font-style: italic;")
        self.result_label.setFixedHeight(320)

        self.preview_row.addWidget(self.image_label, 1)
        self.preview_row.addWidget(self.result_label, 1)
        self.layout.addLayout(self.preview_row)

        # Inline result info
        self.result_info = QLabel("Cells: —")
        self.result_info.setAlignment(Qt.AlignCenter)
        self.result_info.setStyleSheet("""
            QLabel {
                border: 1px solid #888;
                padding: 6px 10px;
                font-weight: 700;
                color: #222;
                background: #f6f6f6;
                border-radius: 6px;
            }
        """)
        self.layout.addWidget(self.result_info)

        # Accept drag & drop on the window
        self.setAcceptDrops(True)

        # Model selector (translated to user-friendly choices)
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("What do you want to segment?"))
        self.model_select = QComboBox()
        self.model_select.addItems([
            "Whole cells (cytoplasm + nuclei)",  # → cyto
            "Nuclei only"                        # → nuclei
        ])
        model_layout.addWidget(self.model_select)
        self.layout.addLayout(model_layout)

        # Output folder (button + label)
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output Folder:"))
        self.output_button = QPushButton("Choose Folder")
        self.output_button.clicked.connect(self.select_output_folder)
        output_layout.addWidget(self.output_button)

        self.output_path_label = QLabel("Not selected")
        self.output_path_label.setStyleSheet("color: gray; font-style: italic;")
        self.output_path_label.setWordWrap(True)
        output_layout.addWidget(self.output_path_label)

        self.layout.addLayout(output_layout)

        # Start / Cancel row
        btn_row = QHBoxLayout()
        self.start_button = QPushButton("Start Analysis")
        self.start_button.clicked.connect(self.start_analysis)
        btn_row.addWidget(self.start_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_analysis)
        self.cancel_button.setEnabled(False)
        btn_row.addWidget(self.cancel_button)

        self.layout.addLayout(btn_row)
        self.central_widget.setLayout(self.layout)

    # ---------- Drag & Drop ----------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            fname = event.mimeData().urls()[0].toLocalFile()
            self.load_image(fname)

    # ---------- Make image area clickable ----------
    def mousePressEvent(self, event):
        """Allow clicking the left image area to open file dialog."""
        if event.button() == Qt.LeftButton:
            widget_pos = self.central_widget.mapFrom(self, event.pos())
            if self.image_label.geometry().contains(widget_pos):
                self.upload_image()
        super().mousePressEvent(event)

    # ---------- UI slots ----------
    def upload_image(self):
        """Open a file dialog to select an image."""
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.tif *.tiff)"
        )
        if fname:
            self.load_image(fname)

    def load_image(self, fname):
        """Set current image and update the preview."""
        self.current_image = fname
        pixmap = QPixmap(fname)
        scaled = pixmap.scaled(
            self.image_label.width(),
            self.image_label.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setStyleSheet("")
        self.image_label.setText("")

    def select_output_folder(self):
        """Open a folder dialog and show the selected path inline."""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            self.output_path_label.setText(folder)
            self.output_path_label.setStyleSheet("color: green; font-weight: bold;")
            self.output_path_label.adjustSize()
            self.output_path_label.repaint()
            QApplication.processEvents()

    def get_model_type(self):
        """Map user-friendly combo choice to internal Cellpose model name."""
        idx = self.model_select.currentIndex()
        return "cyto" if idx == 0 else "nuclei"

    def start_analysis(self):
        """Start background segmentation. Requires image and output folder."""
        if self.is_processing:
            QMessageBox.warning(self, "Warning", "Processing already running!")
            return

        if not self.current_image:
            QMessageBox.warning(self, "Warning", "Please upload an image first!")
            return
        if not os.path.exists(self.current_image):
            QMessageBox.critical(self, "Error", f"File not found: {self.current_image}")
            return

        if not self.output_folder or not os.path.isdir(self.output_folder):
            QMessageBox.warning(self, "Warning", "Please choose an output folder first!")
            return

        # Diameter removed → always None
        diameter = None

        model = self.get_model_type()

        self.is_processing = True
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        self.result_label.setStyleSheet("color: gray;")
        self.result_label.setText("Processing...")

        self.processing_thread = ProcessingThread(
            self.current_image, diameter, model, self.output_folder
        )
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.error.connect(self.on_processing_error)
        self.processing_thread.start()

    def on_processing_finished(self, results):
        """Handle successful completion: show overlay/mask and inline count."""
        self.is_processing = False
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        show_path = results.get("overlay_path") or results.get("mask_path")
        if show_path and os.path.exists(show_path):
            pix = QPixmap(show_path)
            self.result_label.setPixmap(
                pix.scaled(
                    self.result_label.width(),
                    self.result_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )
            self.result_label.setStyleSheet("")
            self.result_label.setText("")
        else:
            self.result_label.setText("No result image found.")
            self.result_label.setStyleSheet("color: red;")

        cell_count = results.get("cell_count", 0)
        self.result_info.setText(f"Cells: {cell_count}")

        mask_path = results.get("mask_path")
        if mask_path and os.path.exists(mask_path):
            try:
                os.remove(mask_path)
            except Exception as e:
                print(f"Warn: could not delete mask file: {e}")

    def on_processing_error(self, message):
        self.is_processing = False
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        QMessageBox.critical(self, "Error", f"Processing failed: {message}")

    def cancel_analysis(self):
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self.processing_thread.wait(1000)
        self.is_processing = False
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
