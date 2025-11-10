# worker.py  —  Cellpose v1.0.2 兼容版（带叠加图输出）
import os
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from cellpose import models, io, utils

class ProcessingThread(QThread):
    finished = pyqtSignal(object)   # dict: {cell_count, mask_path, overlay_path, note?}
    error = pyqtSignal(str)

    def __init__(self, image_path, diameter=None, model="cyto", output_folder="."):
        super().__init__()
        self.image_path = image_path
        self.diameter = diameter
        self.model = (model or "cyto")
        self.output_folder = output_folder or "."
        self._is_running = True

    def run(self):
        try:
            # ---------- 基础校验 ----------
            if not self.image_path or not os.path.exists(self.image_path):
                raise ValueError(f"找不到图像文件：{self.image_path}")

            os.makedirs(self.output_folder, exist_ok=True)

            # ---------- 读图 ----------
            img = io.imread(self.image_path)
            if img is None:
                raise ValueError("无法读取输入图像（io.imread 返回 None）")

            # ---------- GPU 检测（1.0.2 没有 models.use_gpu） ----------
            try:
                import torch
                use_gpu = bool(torch.cuda.is_available())
            except Exception:
                use_gpu = False
            print(f"[Worker] Using GPU: {use_gpu}")

            # ---------- 选择模型类名（兼容 1.0.2 不同命名） ----------
            ModelClass = models.CellposeModel if hasattr(models, "CellposeModel") else models.Cellpose

            # 1.0.2 通常只支持 'cyto' / 'nuclei'，UI 若传 'cyto2' 则回退
            model_type = self.model
            note = None
            if model_type not in ("cyto", "nuclei"):
                note = f"模型类型“{model_type}”在 Cellpose 1.0.2 可能不可用，已回退到 'cyto'"
                model_type = "cyto"

            cp_model = ModelClass(gpu=use_gpu, model_type=model_type)

            # ---------- 分割 ----------
            # 1.0.2 的 eval 通常返回 (masks, flows, styles)
            masks, flows, styles = cp_model.eval(
                [img],
                diameter=self.diameter,
                channels=[0, 0]   # 默认灰度；如需彩色通道可改 [2,3] 等
            )

            if not self._is_running:
                print("[Worker] Processing cancelled.")
                return

            mask = masks[0]
            cell_count = int(mask.max())

            # ---------- 保存输出 ----------
            base = os.path.splitext(os.path.basename(self.image_path))[0]
            mask_path = os.path.join(self.output_folder, f"{base}_masks.png")
            io.imsave(mask_path, mask.astype(np.uint16))

            # --- 生成“原图+红色轮廓”叠加图，便于 UI 预览 ---
            outlines = utils.masks_to_outlines(mask)  # 边界布尔图
            overlay = self._make_overlay(img, outlines)  # 叠加红色边界
            overlay_path = os.path.join(self.output_folder, f"{base}_overlay.png")
            io.imsave(overlay_path, overlay)

            # ---------- 回传结果 ----------
            result = {
                "cell_count": cell_count,
                "mask_path": mask_path,
                "overlay_path": overlay_path
            }
            if note:
                result["note"] = note

            print(f"[Worker] Done. Cells: {cell_count}")
            self.finished.emit(result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))

    def stop(self):
        self._is_running = False

    # ======= 辅助：做一个 RGB 叠加图（原图 + 红色轮廓） =======
    def _make_overlay(self, img, outlines_bool):
        """
        img: np.ndarray, (H,W) 灰度 或 (H,W,3) 彩色
        outlines_bool: (H,W) True 表示边界像素
        return: uint8 RGB
        """
        # 规范到 [0,255] uint8 的 RGB
        if img.ndim == 2:
            # 灰度 -> 3通道
            arr = self._to_uint8(img)
            rgb = np.stack([arr, arr, arr], axis=-1)
        else:
            # 彩色
            rgb = self._to_uint8(img)
            if rgb.shape[-1] == 4:   # RGBA -> RGB
                rgb = rgb[..., :3]

        # 叠加红色轮廓
        overlay = rgb.copy()
        overlay[outlines_bool] = np.array([255, 0, 0], dtype=np.uint8)
        return overlay

    def _to_uint8(self, a):
        """把任意 dtype/范围的图像压到 0..255 的 uint8"""
        a = np.asarray(a)
        if a.dtype == np.uint8:
            return a
        amin, amax = float(np.min(a)), float(np.max(a))
        if amax <= amin:
            return np.zeros_like(a, dtype=np.uint8)
        scaled = (a - amin) / (amax - amin)
        scaled = np.clip(scaled, 0, 1)
        return (scaled * 255.0).astype(np.uint8)
