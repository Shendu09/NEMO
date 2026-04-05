"""
NEMO Model Preloader - Eager Loading for Faster First Inference

Preloads heavy models at server startup to avoid latency on first request.
Runs in background threads to not block server initialization.

Models preloaded:
- PaddleOCR (OCR, ~200MB)
- CLIP (vision-language, ~350MB)
- Florence-2 (foundation model, ~1GB) - optional, can skip
- DistilBART (summarization, ~300MB)
- sentence-transformers (intent matching, ~100MB)

Total: ~1.3GB VRAM on GPU
"""

import logging
import threading
import time
from typing import Callable, List, Optional

logger = logging.getLogger("nemo.preloader")


class ModelPreloader:
    """Eagerly loads models on startup to reduce first-request latency."""
    
    def __init__(self, skip_large: bool = False):
        """
        Args:
            skip_large: Skip florence-2 on first startup (can add later)
        """
        self.skip_large = skip_large
        self.loaded_models: List[str] = []
        self.failed_models: List[tuple[str, str]] = []
        self.start_time = time.time()
        self.lock = threading.Lock()
    
    def preload_all(self) -> dict:
        """Preload all models in parallel threads."""
        logger.info("=" * 60)
        logger.info("🚀 NEMO Model Preloader Starting...")
        logger.info("=" * 60)
        
        threads = []
        
        # Vision models
        threads.append(self._spawn_thread("PaddleOCR", self._load_paddleocr))
        threads.append(self._spawn_thread("CLIP", self._load_clip))
        
        # Only load Florence-2 if not skipping
        if not self.skip_large:
            threads.append(self._spawn_thread("Florence-2", self._load_florence2))
        
        # NLP models  
        threads.append(self._spawn_thread("DistilBART", self._load_distilbart))
        threads.append(self._spawn_thread("sentence-transformers", self._load_intent_matcher))
        
        # Wait for all to complete
        for thread in threads:
            thread.join(timeout=120)  # Max 2 min per model
        
        elapsed = time.time() - self.start_time
        
        # Report
        logger.info("=" * 60)
        logger.info(f"✓ Model Preload Complete ({elapsed:.1f}s)")
        logger.info("=" * 60)
        
        if self.loaded_models:
            logger.info(f"✓ Successfully loaded: {', '.join(self.loaded_models)}")
        
        if self.failed_models:
            logger.warning(f"⚠ Failed to load:")
            for name, error in self.failed_models:
                logger.warning(f"  - {name}: {error}")
        
        return {
            'loaded': self.loaded_models,
            'failed': self.failed_models,
            'elapsed_seconds': elapsed,
        }
    
    def _spawn_thread(self, name: str, fn: Callable) -> threading.Thread:
        """Spawn a background thread for model loading."""
        thread = threading.Thread(target=fn, daemon=True)
        thread.start()
        return thread
    
    def _mark_success(self, name: str) -> None:
        """Mark model as successfully loaded."""
        with self.lock:
            elapsed = time.time() - self.start_time
            logger.info(f"  ✓ {name:<25} [{elapsed:.1f}s]")
            self.loaded_models.append(name)
    
    def _mark_failure(self, name: str, error: str) -> None:
        """Mark model as failed to load."""
        with self.lock:
            elapsed = time.time() - self.start_time
            logger.warning(f"  ✗ {name:<25} [{elapsed:.1f}s] - {error}")
            self.failed_models.append((name, error))
    
    def _load_paddleocr(self) -> None:
        """Preload PaddleOCR."""
        try:
            from core.vision.omniparser_vision import _get_paddleocr_reader
            reader = _get_paddleocr_reader()
            if reader is not None:
                self._mark_success("PaddleOCR")
            else:
                self._mark_failure("PaddleOCR", "Reader is None")
        except Exception as e:
            self._mark_failure("PaddleOCR", str(e))
    
    def _load_clip(self) -> None:
        """Preload CLIP."""
        try:
            from core.vision.omniparser_vision import _get_clip_model
            model = _get_clip_model()
            if model is not None:
                self._mark_success("CLIP")
            else:
                self._mark_failure("CLIP", "Model is None")
        except Exception as e:
            self._mark_failure("CLIP", str(e))
    
    def _load_florence2(self) -> None:
        """Preload Florence-2."""
        try:
            from core.vision.omniparser_vision import _get_florence2_model
            model_data = _get_florence2_model()
            if model_data is not None:
                self._mark_success("Florence-2")
            else:
                self._mark_failure("Florence-2", "Model is None")
        except Exception as e:
            self._mark_failure("Florence-2", str(e))
    
    def _load_distilbart(self) -> None:
        """Preload DistilBART."""
        try:
            from bridge.nemo_server import _get_summarizer
            model = _get_summarizer()
            if model is not None:
                self._mark_success("DistilBART")
            else:
                self._mark_failure("DistilBART", "Model is None")
        except Exception as e:
            self._mark_failure("DistilBART", str(e))
    
    def _load_intent_matcher(self) -> None:
        """Preload sentence-transformers."""
        try:
            from core.service.intent_matcher import IntentMatcher
            matcher = IntentMatcher()
            if matcher is not None:
                self._mark_success("sentence-transformers")
            else:
                self._mark_failure("sentence-transformers", "Matcher is None")
        except Exception as e:
            self._mark_failure("sentence-transformers", str(e))


def preload_models_async(skip_large: bool = False) -> None:
    """Asynchronously preload all models in background."""
    preloader = ModelPreloader(skip_large=skip_large)
    preloader.preload_all()


if __name__ == "__main__":
    # Test preloader
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    preloader = ModelPreloader(skip_large=False)
    results = preloader.preload_all()
    
    print("\nResults:")
    import json
    print(json.dumps(results, indent=2))
