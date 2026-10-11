"""Image and video frame preprocessing utilities."""
from typing import Tuple, Optional
import numpy as np
import cv2


class ImagePreprocessor:
    """Handles resolution-aware resizing, normalization, and ROI masking."""

    def __init__(self, max_dimension: int = 1920):
        self.max_dimension = max_dimension

    def preprocess(
        self,
        image: np.ndarray,
        roi_mask: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, float]:
        """
        Preprocesses an input image (BGR).
        
        Returns:
            processed_image: resized and optionally masked image
            scale_factor: factor applied to coordinates (processed = original * scale)
        """
        if image is None or image.size == 0:
            raise ValueError("Input image is empty or invalid.")

        h, w = image.shape[:2]
        scale = 1.0
        
        # Scale down if exceeds max_dimension
        max_side = max(h, w)
        if max_side > self.max_dimension:
            scale = self.max_dimension / float(max_side)
            new_w = int(round(w * scale))
            new_h = int(round(h * scale))
            processed = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            processed = image.copy()

        # Apply ROI mask if provided
        if roi_mask is not None:
            if roi_mask.shape[:2] != (h, w):
                roi_resized = cv2.resize(
                    roi_mask, 
                    (processed.shape[1], processed.shape[0]), 
                    interpolation=cv2.INTER_NEAREST
                )
            else:
                roi_resized = cv2.resize(
                    roi_mask, 
                    (processed.shape[1], processed.shape[0]), 
                    interpolation=cv2.INTER_NEAREST
                ) if scale != 1.0 else roi_mask

            if len(roi_resized.shape) == 2 and len(processed.shape) == 3:
                mask_3ch = cv2.merge([roi_resized, roi_resized, roi_resized])
                processed = np.where(mask_3ch > 0, processed, 0)
            else:
                processed = np.where(roi_resized > 0, processed, 0)

        return processed, scale
