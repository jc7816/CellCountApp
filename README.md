# Cell Image Segmentation & Analysis App (Cellpose 1.0.2)
This project is a desktop application for **cell image segmentation** and **quantitative cell analysis**, built using **Cellpose 1.0.2** and a custom **PyQt5 GUI**.

Users can load a microscopy image, run segmentation in a CPU-only environment, and compute:
- Total cell count
- Mean cell area (in pixel²)
- Mean cell area (in µm²) if pixel size is provided
- Segmentation overlay of the cell image

All processing runs in a Conda environment with CPU-only PyTorch, ensuring easy installation and high compatibility.

## 🧬 1. Features

- **Drag-and-drop UI** for loading images
- **Cellpose 1.0.2 segmentation** (cyto model)
- **Side-by-side visualisation** of original + segmentation overlay
- **Quantitative metrics**
  - Cell count
  - Mean cell area (px²)
  - Mean cell area (µm²) using user-provided pixel size
- **Responsive UI** with background worker thread
- **CPU-only environment** (no CUDA required)

## 📁 2. Project Structure

```
project_root/
├── UI.py               # PyQt5 GUI
├── worker.py           # QThread worker (Cellpose segmentation + stats)
├── environment.yml     # Conda environment (CPU-only)
├── README.md           # This documentation
└── samples/            # Example test images
```


## 🛠 3. Installation (Conda, CPU-only)

Create and activate the environment:

```
conda env create -f environment.yml
```
```
conda activate cellpose_cpu
```
### Important Notes

- Please run these commands **in Anaconda Prompt**, not in Windows CMD or PowerShell.
- Make sure you **cd into the directory that contains `environment.yml`** before creating the environment:

```
cd path/to/your/project
```

## ▶️ 4. How to Run
```
python UI.py
```
Steps:

- Upload an image
- Choose output folder
- (Optional) Enter pixel size (µm/pixel)
- Click Start Analysis
- View overlay + cell count + area

## 🧩 5. Implementation Notes

- Uses Cellpose 1.0.2 with model_type="cyto", gpu=False
- Worker runs in QThread
- Area calculation uses np.unique(mask, return_counts=True)
- µm² area = px_area * (pixel_size ** 2)

## ⚠️ 6. Limitations

- CPU-only
- Single-image processing
- Only “cyto” model
- No batch/3D segmentation

## 🚀 7. Future Improvements

- GPU acceleration
- Batch processing
- Stronger models
- Morphology metrics
- .exe packaging

## 📚 8. References

Stringer et al. (2021). Cellpose: a generalist algorithm for cellular segmentation.
Nature Methods.

https://github.com/MouseLand/cellpose



