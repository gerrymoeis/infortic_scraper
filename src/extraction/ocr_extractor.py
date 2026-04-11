"""
OCR Extractor for extracting text from images
"""

import sys
from pathlib import Path
from typing import Optional
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import pytesseract
    from PIL import Image
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
            # Check if file exists
            if not Path(image_path).exists():
                logger.warning(f"Image file not found: {image_path}")
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
