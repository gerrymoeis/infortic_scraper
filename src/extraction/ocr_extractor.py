"""
OCR Extractor for extracting text from images
Enhanced with preprocessing for better accuracy (Phase A)
"""

import sys
from pathlib import Path
from typing import Optional, List, Tuple
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import pytesseract
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from src.extraction.utils.logger import setup_logger

logger = setup_logger('ocr')

class OCRExtractor:
    """Extract text from images using Tesseract OCR"""
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Initialize OCR extractor
        
        Args:
            tesseract_cmd: Path to tesseract executable (optional)
                          If not provided, assumes tesseract is in PATH
        """
        if not OCR_AVAILABLE:
            logger.warning("OCR dependencies not installed. Install with: pip install pytesseract pillow")
            self.available = False
            return
        
        self.available = True
        
        # Set tesseract command path if provided
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        # Test if tesseract is available
        try:
            pytesseract.get_tesseract_version()
            logger.info("Tesseract OCR initialized successfully")
        except Exception as e:
            logger.error(f"Tesseract not found: {e}")
            logger.error("Please install Tesseract OCR:")
            logger.error("  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
            logger.error("  Mac: brew install tesseract")
            logger.error("  Linux: sudo apt-get install tesseract-ocr")
            self.available = False
    
    def extract_with_preprocessing(self, image_path: str, preprocess: List[str] = None, timeout: int = 10) -> Optional[str]:
        """
        Extract text with image preprocessing for better accuracy (Phase A Enhancement)
        
        Preprocessing techniques based on research:
        - Rotate: Auto-corrects orientation using EXIF data
        - Grayscale: Simplifies image, improves OCR accuracy
        - Contrast: Enhances text visibility (1.5x recommended by research)
        - Brightness: Adjusts for poor lighting (1.2x recommended by research)
        - Denoise: Removes background noise using median filter
        - Threshold: Binary thresholding for better text clarity
        
        Args:
            image_path: Path to image file
            preprocess: List of preprocessing steps to apply
                       Default: ['rotate', 'grayscale', 'contrast', 'brightness']
            timeout: Maximum processing time in seconds (increased from 5 to 10)
        
        Returns:
            Extracted text or None if failed
        """
        if not self.available:
            return None
        
        try:
            # Check if file exists - ENHANCED LOGGING (Phase 1)
            image_path_obj = Path(image_path)
            if not image_path_obj.exists():
                # Enhanced error logging with full diagnostic info
                logger.warning(f"[OCR] Image not found: {image_path_obj.name}")
                logger.warning(f"[OCR] Full path: {image_path_obj.absolute()}")
                logger.warning(f"[OCR] Working directory: {Path.cwd()}")
                logger.warning(f"[OCR] Parent directory exists: {image_path_obj.parent.exists()}")
                if image_path_obj.parent.exists():
                    # List files in parent directory for debugging
                    files_in_dir = list(image_path_obj.parent.glob('*'))[:5]
                    logger.warning(f"[OCR] Files in directory (first 5): {[f.name for f in files_in_dir]}")
                return None
            
            # Open image
            img = Image.open(image_path)
            
            # Default preprocessing if none specified
            if preprocess is None:
                preprocess = ['rotate', 'grayscale', 'contrast', 'brightness']
            
            # Apply preprocessing in order
            if 'rotate' in preprocess:
                # Auto-rotate based on EXIF data
                img = ImageOps.exif_transpose(img)
            
            if 'grayscale' in preprocess:
                # Convert to grayscale (improves OCR accuracy)
                img = img.convert('L')
            
            if 'contrast' in preprocess:
                # Increase contrast by 50% (research-backed value)
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)
            
            if 'brightness' in preprocess:
                # Increase brightness by 20% (research-backed value)
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(1.2)
            
            if 'denoise' in preprocess:
                # Remove noise with median filter
                img = img.filter(ImageFilter.MedianFilter(size=3))
            
            if 'threshold' in preprocess:
                # Binary thresholding for better text clarity
                # Convert to grayscale first if not already
                if img.mode != 'L':
                    img = img.convert('L')
                # Simple threshold at mean value
                import numpy as np
                img_array = np.array(img)
                threshold = np.mean(img_array)
                img_array = ((img_array > threshold) * 255).astype(np.uint8)
                img = Image.fromarray(img_array)
            
            # Extract text with multiple language packs
            # Indonesian first (primary), then English, then Javanese
            text = pytesseract.image_to_string(
                img,
                lang='ind+eng+jav',  # Indonesian + English + Javanese
                timeout=timeout,
                config='--psm 6'  # PSM 6: Assume uniform block of text (best for posters)
            )
            
            if text and text.strip():
                logger.debug(f"[OCR-PREPROCESS] Extracted {len(text)} chars from {Path(image_path).name}")
                return text.strip()
            
            return None
        
        except pytesseract.TesseractNotFoundError:
            logger.error("Tesseract executable not found. Please install Tesseract OCR.")
            self.available = False
            return None
        
        except Exception as e:
            logger.warning(f"[OCR-PREPROCESS] Failed for {Path(image_path).name}: {type(e).__name__}: {str(e)[:100]}")
            return None
    
    def extract_with_confidence(self, image_path: str, timeout: int = 10) -> Tuple[Optional[str], int]:
        """
        Extract text and return confidence score (Phase A Enhancement)
        
        Args:
            image_path: Path to image file
            timeout: Maximum processing time in seconds
        
        Returns:
            Tuple of (extracted_text, confidence_score 0-100)
        """
        if not self.available:
            return None, 0
        
        try:
            # Check if file exists - ENHANCED LOGGING (Phase 1)
            image_path_obj = Path(image_path)
            if not image_path_obj.exists():
                logger.warning(f"[OCR] Image not found: {image_path_obj.name}")
                logger.warning(f"[OCR] Full path: {image_path_obj.absolute()}")
                return None, 0
            
            # Open and preprocess image
            img = Image.open(image_path)
            
            # Apply default preprocessing
            img = ImageOps.exif_transpose(img)
            img = img.convert('L')
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
            
            # Get detailed OCR data with confidence
            data = pytesseract.image_to_data(
                img,
                lang='ind+eng+jav',
                timeout=timeout,
                config='--psm 6',
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text and calculate average confidence
            texts = []
            confidences = []
            
            for i, conf in enumerate(data['conf']):
                if int(conf) > 0:  # Valid confidence
                    text = data['text'][i].strip()
                    if text:
                        texts.append(text)
                        confidences.append(int(conf))
            
            if texts:
                full_text = ' '.join(texts)
                avg_confidence = sum(confidences) // len(confidences) if confidences else 0
                logger.debug(f"[OCR-CONFIDENCE] {Path(image_path).name}: {avg_confidence}% confidence, {len(full_text)} chars")
                return full_text, avg_confidence
            
            return None, 0
        
        except pytesseract.TesseractNotFoundError:
            logger.error("Tesseract executable not found. Please install Tesseract OCR.")
            self.available = False
            return None, 0
        
        except Exception as e:
            logger.warning(f"[OCR-CONFIDENCE] Failed for {Path(image_path).name}: {type(e).__name__}: {str(e)[:100]}")
            return None, 0
    
    def extract_text(self, image_path: str, timeout: int = 5) -> Optional[str]:
        """
        Extract text from image using OCR
        
        Args:
            image_path: Path to image file
            timeout: Maximum processing time in seconds
            
        Returns:
            Extracted text or None if failed
        """
        if not self.available:
            return None
        
        try:
            # Check if file exists - ENHANCED LOGGING (Phase 1)
            image_path_obj = Path(image_path)
            if not image_path_obj.exists():
                logger.warning(f"[OCR] Image not found: {image_path_obj.name}")
                logger.warning(f"[OCR] Full path: {image_path_obj.absolute()}")
                return None
            
            # Open image
            img = Image.open(image_path)
            
            # Extract text with Indonesian language support
            # Use both English and Indonesian for better results
            text = pytesseract.image_to_string(
                img, 
                lang='eng+ind',  # English + Indonesian
                timeout=timeout
            )
            
            if text and text.strip():
                logger.debug(f"OCR extracted {len(text)} characters from {Path(image_path).name}")
                return text.strip()
            else:
                logger.debug(f"OCR found no text in {Path(image_path).name}")
                return None
                
        except pytesseract.TesseractNotFoundError:
            logger.error("Tesseract executable not found. Please install Tesseract OCR.")
            self.available = False
            return None
            
        except Exception as e:
            logger.warning(f"OCR failed for {Path(image_path).name}: {type(e).__name__}: {str(e)[:100]}")
            return None
    
    def extract_text_from_multiple(self, image_paths: list, timeout: int = 5) -> dict:
        """
        Extract text from multiple images
        
        Args:
            image_paths: List of image file paths
            timeout: Maximum processing time per image
            
        Returns:
            Dictionary mapping image_path to extracted text
        """
        results = {}
        
        for image_path in image_paths:
            text = self.extract_text(image_path, timeout)
            if text:
                results[image_path] = text
        
        return results


def test_ocr():
    """Test OCR functionality"""
    print("Testing OCR Extractor...")
    
    extractor = OCRExtractor()
    
    if not extractor.available:
        print("❌ OCR not available")
        return False
    
    print("✅ OCR initialized successfully")
    
    # Test with a sample image if available
    test_image = Path(__file__).parent.parent.parent / 'data' / 'images'
    if test_image.exists():
        images = list(test_image.glob('*.jpg')) + list(test_image.glob('*.webp'))
        if images:
            print(f"\nTesting with {images[0].name}...")
            text = extractor.extract_text(str(images[0]))
            if text:
                print(f"✅ Extracted {len(text)} characters")
                print(f"Preview: {text[:200]}...")
            else:
                print("⚠️  No text extracted")
    
    return True


if __name__ == '__main__':
    test_ocr()
