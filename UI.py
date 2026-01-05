
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFileDialog, QMessageBox, QApplication, QLineEdit
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import os
from worker import ProcessingThread


class CellposeApp(QMainWindow):
    """
    Features:
        - Drag & drop or click to upload an image.
        - Fixed Cellpose model for simplicity.
        - Choose an output folder.
        - Optional pixel size input to convert mean area from px^2 to µm^2.
        - Run Cellpose in a background thread.
        - Show original image (left) and overlay result (right).
        - Show cell count and mean area (px^2 and optionally µm^2).
    """
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

        # Preview row: input on left, result on right 
        self.preview_row = QHBoxLayout()

        # Input image area
        self.image_label = QLabel("Drag & Drop or Click to Upload Image")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 2px dashed gray;")
        self.image_label.setFixedHeight(320)

        # Result image area
        self.result_label = QLabel("Segmentation Result will appear here")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet(
            "border: 2px dashed gray; color: gray; font-style: italic;"
        )
        self.result_label.setFixedHeight(320)

        self.preview_row.addWidget(self.image_label, 1)
        self.preview_row.addWidget(self.result_label, 1)
        self.layout.addLayout(self.preview_row)

        # Inline result info (cell count + areas) with larger font
        self.result_info = QLabel("Cells: —    Mean area: —")
        self.result_info.setAlignment(Qt.AlignCenter)
        self.result_info.setStyleSheet("""
            QLabel {
                border: 1px solid #888;
                padding: 8px 12px;
                font-weight: 700;
                font-size: 24px;
                color: #222;
                background: #f6f6f6;
                border-radius: 6px;
            }
        """)
        self.layout.addWidget(self.result_info)

        # Accept drag & drop on the window
        self.setAcceptDrops(True)

        # Pixel size input (optional)
        pixel_layout = QHBoxLayout()
        pixel_layout.addWidget(QLabel("Pixel size (µm/pixel, optional):"))
        self.pixel_size_input = QLineEdit()
        pixel_layout.addWidget(self.pixel_size_input)
        self.layout.addLayout(pixel_layout)

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
        if event.button() == Qt.LeftButton:
            widget_pos = self.central_widget.mapFrom(self, event.pos())
            if self.image_label.geometry().contains(widget_pos):
                self.upload_image()
        super().mousePressEvent(event)

    # ---------- UI ----------
    def upload_image(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.tif *.tiff)"
        )
        if fname:
            self.load_image(fname)

    def load_image(self, fname):
        """Set current image and update the preview"""
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
        self.result_info.setText("Cells: —    Mean area: —")

    def reset_result_preview(self):
        self.result_label.clear()                 
        self.result_label.setPixmap(QPixmap())    
        self.result_label.setText("Segmentation Result will appear here")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet("border: 2px dashed gray; color: gray; font-style: italic;")


    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            self.output_path_label.setText(folder)
            self.output_path_label.setStyleSheet("color: green; font-weight: bold;")
            self.output_path_label.adjustSize()
            self.output_path_label.repaint()
            QApplication.processEvents()

    def start_analysis(self):
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

        diameter = None

        # Fixed model
        model = "cyto"

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
        self.is_processing = False
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        # Show result image
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

        # Extract metrics
        cell_count = results.get("cell_count", 0)
        mean_area_px = results.get("mean_area_px", 0.0)

        # Try to compute mean area in µm^2 if pixel size is provided
        pixel_size_text = self.pixel_size_input.text().strip()
        mean_area_um2 = None
        if pixel_size_text:
            try:
                px_size = float(pixel_size_text)
                if px_size > 0:
                    mean_area_um2 = mean_area_px * (px_size ** 2)
            except ValueError:
                mean_area_um2 = None  # ignore invalid value, just show px^2

        # Build result info text
        if mean_area_um2 is not None:
            text = (
                f"Cells: {cell_count}    "
                f"Mean area: {mean_area_px:.1f} px^2 "
                f"({mean_area_um2:.2f} µm^2)"
            )
        else:
            text = f"Cells: {cell_count}    Mean area: {mean_area_px:.1f} px^2"

        self.result_info.setText(text)

        # Auto-delete mask file after finishing 
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
        self.result_label.setText("Segmentation Result will appear here")
        self.result_info.setText("Cells: —    Mean area: —")
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
