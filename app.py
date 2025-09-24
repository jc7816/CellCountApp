import numpy as np
from cellpose import models, io
from PIL import Image
import matplotlib.pyplot as plt
from cellpose.models import CellposeModel
from cellpose import models

# Path to the image file you want to segment
img_path = r'E:\cellPoseEn\cell_mammal.png'

# Load image as numpy array
img = io.imread(img_path)  # cellpose.io can read tif, png, jpg, etc.

# Initialize the Cellpose model
model = models.CellposeModel()
print("Device in use:", model.device)
# Set segmentation parameters
diameter = None          # Estimated cell diameter in pixels. Set 0 for auto mode.
channels = [0, 0]        # List of channels: [cytoplasm_channel, nucleus_channel]. [0,0] for grayscale.


# Run segmentation
# The model expects a list of images (even if only one image)
results = model.eval([img], diameter=diameter)
masks = results['masks']
flows = results['flows']
diams = results['diams']

# Show original image and segmentation mask using matplotlib
fig, axs = plt.subplots(1, 2, figsize=(10, 5))
axs[0].imshow(img if img.ndim == 2 else img[..., 0], cmap='gray')
axs[0].set_title('Original Image')
axs[0].axis('off')

axs[1].imshow(masks[0], cmap='nipy_spectral')
axs[1].set_title('Cellpose Mask')
axs[1].axis('off')

plt.tight_layout()
plt.show()

# Print summary information
print(f"Number of detected objects: {int(masks[0].max())}")
print(f"Estimated cell diameter: {float(diams)}")