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
        """Initialize unified AI client with OpenRouter and Gemini"""
        self.gemini_client = GeminiClient()
        
        # Initialize OpenRouter only if keys are available
        self.openrouter_client = None
        if config.OPENROUTER_API_KEYS:
            try:
                self.openrouter_client = OpenRouterClient()
                logger.info(f"[OPENROUTER] Initialized with {len(config.OPENROUTER_API_KEYS)} API key(s)")
            except Exception as e:
                logger.warning(f"[OPENROUTER] Could not initialize: {e}")
                logger.warning(f"[OPENROUTER] Continuing with Gemini only")
        else:
            logger.info("[OPENROUTER] No API keys configured")
        
        # Log primary service configuration
        if config.PRIMARY_SERVICE == 'openrouter' and self.openrouter_client:
            logger.info(f"[CONFIG] PRIMARY: OpenRouter Free | FALLBACK: Gemini API")
        else:
            logger.info(f"[CONFIG] PRIMARY: Gemini API | FALLBACK: OpenRouter" if self.openrouter_client else "[CONFIG] Gemini API only")
    
    def process_batch(self, captions_batch: List[Dict], ocr_texts: Dict[str, tuple] = None, send_images: bool = True) -> List[Dict]:
        """
        Process a batch of captions with automatic fallback
        
        NEW STRATEGY: OpenRouter PRIMARY, Gemini FALLBACK
        - Faster failover (3 attempts per service vs 10)
        - Reduced backoff (max 10s vs 30s)
        - Better timeout handling for GitHub Actions
        
        Flow:
        1. Try PRIMARY service (OpenRouter or Gemini based on config)
        2. If PRIMARY fails, try FALLBACK service
        3. Return results or empty list
        
        Args:
            captions_batch: List of caption dictionaries
            ocr_texts: Optional dict mapping post_id to (ocr_text, confidence) tuples
            send_images: If True, send actual images to API
            
        Returns:
            List of extracted data dictionaries
        """
        
        # Determine primary and fallback services based on config
        if config.PRIMARY_SERVICE == 'openrouter' and self.openrouter_client:
            primary_name = "OpenRouter"
            primary_client = self.openrouter_client
            fallback_name = "Gemini"
            fallback_client = self.gemini_client
        else:
            primary_name = "Gemini"
            primary_client = self.gemini_client
            fallback_name = "OpenRouter"
            fallback_client = self.openrouter_client
        
        # Try PRIMARY service first
        logger.info(f"[PRIMARY] Trying {primary_name} for {len(captions_batch)} posts...")
        
        try:
            results = primary_client.process_batch(captions_batch, ocr_texts, send_images)
            
            if results:
                logger.info(f"[PRIMARY] ✓ {primary_name} succeeded: {len(results)} items extracted")
                return results
            else:
                logger.warning(f"[PRIMARY] ✗ {primary_name} returned no results")
        
        except KeyboardInterrupt:
            # Don't catch keyboard interrupt - let it propagate
            raise
        
        except Exception as e:
            logger.warning(f"[PRIMARY] ✗ {primary_name} failed with exception: {str(e)[:100]}")
        
        # If PRIMARY failed and FALLBACK is available
        if fallback_client:
            logger.warning(f"[FALLBACK] {primary_name} failed, trying {fallback_name}...")
            
            try:
                results = fallback_client.process_batch(captions_batch, ocr_texts, send_images)
                
                if results:
                    logger.info(f"[FALLBACK] ✓ {fallback_name} succeeded: {len(results)} items extracted")
                    return results
                else:
                    logger.error(f"[FALLBACK] ✗ {fallback_name} returned no results")
            
            except KeyboardInterrupt:
                # Don't catch keyboard interrupt - let it propagate
                raise
            
            except Exception as e:
                logger.error(f"[FALLBACK] ✗ {fallback_name} failed with exception: {str(e)[:100]}")
        
        # Both failed (or fallback not available)
        if fallback_client:
            logger.error(f"[ERROR] ✗ Both {primary_name} and {fallback_name} failed for this batch")
        else:
            logger.error(f"[ERROR] ✗ {primary_name} failed and no fallback available")
        
        return []
