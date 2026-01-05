
import os
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from cellpose import models, io, utils


class ProcessingThread(QThread):
    """
    Background processing thread that runs Cellpose segmentation on CPU.

    Emits:
        finished(dict): {
            "cell_count": int,
            "mean_area_px": float,
            "mask_path": str,
            "overlay_path": str
        }
        error(str): error message
    """
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, image_path, diameter=None, model="cyto", output_folder="."):
        super().__init__()
        self.image_path = image_path
        self.diameter = diameter        # currently not used (None), kept for future extension
        self.model = model              # "cyto" or "nuclei"
        self.output_folder = output_folder or "."
        self._is_running = True

    def run(self):
        try:
            if not self.image_path or not os.path.exists(self.image_path):
                raise ValueError(f"Image file not found: {self.image_path}")

            os.makedirs(self.output_folder, exist_ok=True)

            img = io.imread(self.image_path)
            if img is None:
                raise ValueError("Failed to read image (io.imread returned None)")

            # --- Force CPU (no GPU for now) ---
            use_gpu = False
            print(f"[Worker] Using GPU: {use_gpu}")

            ModelClass = models.CellposeModel if hasattr(models, "CellposeModel") else models.Cellpose
            cp_model = ModelClass(gpu=use_gpu, model_type=self.model)

            # --- Segmentation ---
            masks, flows, styles = cp_model.eval(
                [img],
                diameter=self.diameter,
                channels=[0, 0]  # default: grayscale. Adjust here if you need color channels.
            )

            if not self._is_running:
                print("[Worker] Processing cancelled.")
                return

            mask = masks[0]

            # ---- Compute cell_count and mean area in pixels ----
            # labels: unique values in mask, counts: number of pixels for each label
            labels, counts = np.unique(mask, return_counts=True)
            if labels.size > 0 and labels[0] == 0:
                labels = labels[1:]
                counts = counts[1:]

            cell_count = int(len(labels))
            if cell_count > 0 and counts.size > 0:
                mean_area_px = float(counts.mean())  # average number of pixels per cell
            else:
                mean_area_px = 0.0

            # --- Save results ---
            base = os.path.splitext(os.path.basename(self.image_path))[0]
            mask_path = os.path.join(self.output_folder, f"{base}_masks.png")
            io.imsave(mask_path, mask.astype(np.uint16))

            # --- Build overlay preview ---
            outlines = utils.masks_to_outlines(mask)  # boolean boundary map
            overlay = self._make_overlay(img, outlines)
            overlay_path = os.path.join(self.output_folder, f"{base}_overlay.png")
            io.imsave(overlay_path, overlay)

            result = {
                "cell_count": cell_count,
                "mean_area_px": mean_area_px,
                "mask_path": mask_path,        # UI may delete this after showing overlay
                "overlay_path": overlay_path
            }

            print(f"[Worker] Done. Cells: {cell_count}, Mean area: {mean_area_px:.2f} px^2")
            self.finished.emit(result)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))

    def stop(self):
        self._is_running = False

    def _make_overlay(self, img, outlines_bool):
        if img.ndim == 2:
            arr = self._to_uint8(img)
            rgb = np.stack([arr, arr, arr], axis=-1)
        else:
            rgb = self._to_uint8(img)
            if rgb.shape[-1] == 4:
                rgb = rgb[..., :3]

        overlay = rgb.copy()
        overlay[outlines_bool] = np.array([255, 0, 0], dtype=np.uint8)
        return overlay

    def _to_uint8(self, a):
        a = np.asarray(a)
        if a.dtype == np.uint8:
            return a
        amin, amax = float(np.min(a)), float(np.max(a))
        if amax <= amin:
            return np.zeros_like(a, dtype=np.uint8)
        scaled = (a - amin) / (amax - amin)
        scaled = np.clip(scaled, 0, 1)
        return (scaled * 255.0).astype(np.uint8)
