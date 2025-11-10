from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QLineEdit, QComboBox, QFileDialog, QMessageBox, QApplication
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
import os
import torch
from worker import ProcessingThread

class CellposeApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # 1) 窗口标题改名为 Cell Count
        self.setWindowTitle("Cell Count")
        self.setGeometry(200, 200, 1000, 700)

        self.processing_thread = None
        self.current_image = None
        self.output_folder = None
        self.is_processing = False

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()

        # 预览区域：左右对比（左：原图，右：分割结果）
        self.preview_row = QHBoxLayout()

        # 左侧原图（带拖拽提示）
        self.image_label = QLabel("Drag & Drop or Click to Upload Image")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 2px dashed gray;")
        self.image_label.setFixedHeight(320)

        # 右侧结果图（初始为空）
        self.result_label = QLabel("Result will appear here")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet("border: 2px dashed gray; color: gray; font-style: italic;")
        self.result_label.setFixedHeight(320)

        self.preview_row.addWidget(self.image_label, 1)
        self.preview_row.addWidget(self.result_label, 1)
        self.layout.addLayout(self.preview_row)

        # 启用拖拽到窗口
        self.setAcceptDrops(True)

        # 上传按钮
        self.upload_button = QPushButton("Upload Image")
        self.upload_button.clicked.connect(self.upload_image)
        self.layout.addWidget(self.upload_button)

        # Diameter 输入
        diameter_layout = QHBoxLayout()
        diameter_layout.addWidget(QLabel("Estimated Diameter (px):"))
        self.diameter_input = QLineEdit()
        diameter_layout.addWidget(self.diameter_input)
        self.layout.addLayout(diameter_layout)

        # 模型下拉
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Select Model:"))
        self.model_select = QComboBox()
        # 你当前 cellpose 1.0.2 建议用 cyto/nuclei，UI 可以保留 cyto2；worker 会必要时回退
        self.model_select.addItems(["cyto", "nuclei", "cyto2"])
        model_layout.addWidget(self.model_select)
        self.layout.addLayout(model_layout)

        # 输出文件夹（按钮 + 路径显示）
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

        # 开始 & 取消
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

    # ---------------- Drag & Drop ----------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            fname = event.mimeData().urls()[0].toLocalFile()
            self.load_image(fname)

    # ---------------- UI slots ----------------
    def upload_image(self):
        """Load an image and show in preview"""
        fname, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.tif *.tiff)")
        if fname:
            self.load_image(fname)

    def load_image(self, fname):
        """Helper to set current image"""
        self.current_image = fname
        pixmap = QPixmap(fname)
        self.image_label.setPixmap(
            pixmap.scaled(self.image_label.width(), self.image_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        # 4) 上传完图片后，去掉虚线提示
        self.image_label.setStyleSheet("")           # 去掉边框
        self.image_label.setText("")                 # 去掉文字
        # 显示前一次结果可能保留，若想清空右侧可解除下行注释
        # self.clear_result_preview()

    def select_output_folder(self):
        """Choose an output directory"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder
            self.output_path_label.setText(folder)
            self.output_path_label.setStyleSheet("color: green; font-weight: bold;")
            # 强制刷新，确保实时显示
            self.output_path_label.adjustSize()
            self.output_path_label.repaint()
            QApplication.processEvents()

    def start_analysis(self):
        """Start processing in a background thread"""
        if self.is_processing:
            QMessageBox.warning(self, "Warning", "Processing already running!")
            return

        # 无图像
        if not self.current_image:
            QMessageBox.warning(self, "Warning", "Please upload an image first!")
            return
        if not os.path.exists(self.current_image):
            QMessageBox.critical(self, "Error", f"File not found: {self.current_image}")
            return

        # 2) 未选择输出文件夹 -> 与未选图片相同逻辑，弹警告
        if not self.output_folder or not os.path.isdir(self.output_folder):
            QMessageBox.warning(self, "Warning", "Please choose an output folder first!")
            return

        # 警告 CPU 运行
        if not torch.cuda.is_available():
            QMessageBox.warning(self, "Warning", "No GPU detected. Running on CPU. This may be slow.")

        diameter_text = self.diameter_input.text()
        try:
            diameter = float(diameter_text) if diameter_text else None
        except ValueError:
            QMessageBox.warning(self, "Warning", "Diameter must be a number.")
            return

        model = self.model_select.currentText()
        output_folder = self.output_folder

        self.is_processing = True
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        # 清空右侧结果框的虚线并提示“处理中”（可选）
        self.result_label.setStyleSheet("color: gray;")
        self.result_label.setText("Processing...")

        self.processing_thread = ProcessingThread(self.current_image, diameter, model, output_folder)
        self.processing_thread.finished.connect(self.on_processing_finished)
        self.processing_thread.error.connect(self.on_processing_error)
        self.processing_thread.start()

    def on_processing_finished(self, results):
        """Handle finished processing"""
        self.is_processing = False
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        # 结果信息
        cell_count = results.get("cell_count", 0)
        msg = f"Processing finished!\nCell count: {cell_count}"
        if "note" in results:
            msg += f"\n\nNOTE: {results['note']}"
        QMessageBox.information(self, "Done", msg)

        # 3) 左右对比：右侧显示 overlay（如果有），否则显示 mask
        show_path = results.get("overlay_path") or results.get("mask_path") or results.get("output_path")
        if show_path and os.path.exists(show_path):
            pix = QPixmap(show_path)
            self.result_label.setPixmap(
                pix.scaled(self.result_label.width(), self.result_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.result_label.setStyleSheet("")   # 去掉虚线
            self.result_label.setText("")
        else:
            self.result_label.setText("No result image found.")
            self.result_label.setStyleSheet("color: red;")

    def on_processing_error(self, message):
        """Handle errors during processing"""
        self.is_processing = False
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        QMessageBox.critical(self, "Error", f"Processing failed: {message}")

    def cancel_analysis(self):
        """Stop the processing thread"""
        if self.processing_thread and self.processing_thread.isRunning():
            self.processing_thread.stop()
            self.processing_thread.wait(1000)
        self.is_processing = False
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    # 可选：清空右侧结果
    def clear_result_preview(self):
        self.result_label.clear()
        self.result_label.setText("Result will appear here")
        self.result_label.setStyleSheet("border: 2px dashed gray; color: gray; font-style: italic;")
