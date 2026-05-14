"""
Unified AI Client with automatic fallback support
Tries Gemini first, then OpenRouter if Gemini fails
"""

import sys
from pathlib import Path
from typing import List, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.extraction.gemini_client import GeminiClient
from src.extraction.openrouter_client import OpenRouterClient
from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger

logger = setup_logger('ai_client')

class AIClient:
    def __init__(self):
        """Initialize unified AI client with Gemini and OpenRouter"""
        self.gemini_client = GeminiClient()
        
        # Initialize OpenRouter only if fallback is enabled and keys are available
        self.openrouter_client = None
        if config.USE_OPENROUTER_FALLBACK and config.OPENROUTER_API_KEYS:
            try:
                self.openrouter_client = OpenRouterClient()
                logger.info(f"[FALLBACK] OpenRouter fallback enabled ({len(config.OPENROUTER_API_KEYS)} keys)")
            except Exception as e:
                logger.warning(f"[FALLBACK] Could not initialize OpenRouter: {e}")
                logger.warning(f"[FALLBACK] Continuing with Gemini only")
        else:
            if not config.USE_OPENROUTER_FALLBACK:
                logger.info("[FALLBACK] OpenRouter fallback disabled by config")
            elif not config.OPENROUTER_API_KEYS:
                logger.info("[FALLBACK] OpenRouter fallback disabled (no API keys)")
    
    def process_batch(self, captions_batch: List[Dict], ocr_texts: Dict[str, tuple] = None, send_images: bool = True) -> List[Dict]:
        """
        Process a batch of captions with automatic fallback
        
        Flow:
        1. Try Gemini API (primary)
        2. If Gemini fails completely, try OpenRouter (fallback)
        3. Return results or empty list
        
        Args:
            captions_batch: List of caption dictionaries
            ocr_texts: Optional dict mapping post_id to (ocr_text, confidence) tuples
            send_images: If True, send actual images to API
            
        Returns:
            List of extracted data dictionaries
        """
        
        # Try Gemini first (PRIMARY)
        logger.info(f"[PRIMARY] Trying Gemini API for {len(captions_batch)} posts...")
        
        try:
            results = self.gemini_client.process_batch(captions_batch, ocr_texts, send_images)
            
            if results:
                logger.info(f"[PRIMARY] ✓ Gemini succeeded: {len(results)} items extracted")
                return results
            else:
                logger.warning(f"[PRIMARY] ✗ Gemini returned no results")
        
        except KeyboardInterrupt:
            # Don't catch keyboard interrupt - let it propagate
            raise
        
        except Exception as e:
            logger.warning(f"[PRIMARY] ✗ Gemini failed with exception: {str(e)[:100]}")
        
        # If Gemini failed and OpenRouter fallback is available
        if self.openrouter_client:
            logger.warning(f"[FALLBACK] Gemini failed, trying OpenRouter...")
            
            try:
                results = self.openrouter_client.process_batch(captions_batch, ocr_texts, send_images)
                
                if results:
                    logger.info(f"[FALLBACK] ✓ OpenRouter succeeded: {len(results)} items extracted")
                    return results
                else:
                    logger.error(f"[FALLBACK] ✗ OpenRouter returned no results")
            
            except KeyboardInterrupt:
                # Don't catch keyboard interrupt - let it propagate
                raise
            
            except Exception as e:
                logger.error(f"[FALLBACK] ✗ OpenRouter failed with exception: {str(e)[:100]}")
        
        # Both failed (or OpenRouter not available)
        if self.openrouter_client:
            logger.error(f"[ERROR] ✗ Both Gemini and OpenRouter failed for this batch")
        else:
            logger.error(f"[ERROR] ✗ Gemini failed and no fallback available")
        
        return []
