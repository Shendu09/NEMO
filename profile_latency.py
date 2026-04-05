#!/usr/bin/env python
"""
NEMO Pipeline Latency Profiler - Phase C Optimization

Measures end-to-end latency and identifies bottlenecks:
- Model loading (first run vs cached)
- PaddleOCR inference
- Florence-2 inference  
- CLIP inference
- Intent matching
- Summarization
- Full pipeline

Outputs: latency_profile.json with detailed timing breakdown
"""

import json
import time
import base64
import logging
from pathlib import Path
from typing import Any
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Colors for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def profile_model_loading():
    """Measure model loading latencies."""
    logger.info(f"\n{BLUE}[1/7] Profiling Model Loading...{RESET}")
    results = {}
    
    # Clear model cache (simulate first run)
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    # PaddleOCR (first load)
    logger.info("  • PaddleOCR (first load)...", end=" ", flush=True)
    start = time.time()
    try:
        from core.vision.omniparser_vision import _get_paddleocr_reader
        reader = _get_paddleocr_reader()
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['paddleocr_first_load'] = elapsed
    except Exception as e:
        logger.info(f"SKIP (error: {e})")
        results['paddleocr_first_load'] = None
    
    # PaddleOCR (cached)
    logger.info("  • PaddleOCR (cached)...", end=" ", flush=True)
    start = time.time()
    try:
        from core.vision.omniparser_vision import _get_paddleocr_reader
        reader = _get_paddleocr_reader()
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.1f}ms{RESET}")
        results['paddleocr_cached'] = elapsed
    except Exception as e:
        logger.info(f"SKIP")
        results['paddleocr_cached'] = None
    
    # CLIP (first load)
    logger.info("  • CLIP (first load)...", end=" ", flush=True)
    start = time.time()
    try:
        from core.vision.omniparser_vision import _get_clip_model
        model = _get_clip_model()
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['clip_first_load'] = elapsed
    except Exception as e:
        logger.info(f"SKIP")
        results['clip_first_load'] = None
    
    # Florence-2 (first load)
    logger.info("  • Florence-2 (first load)...", end=" ", flush=True)
    start = time.time()
    try:
        from core.vision.omniparser_vision import _get_florence2_model
        model = _get_florence2_model()
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['florence2_first_load'] = elapsed
    except Exception as e:
        logger.info(f"SKIP")
        results['florence2_first_load'] = None
    
    # DistilBART (first load)
    logger.info("  • DistilBART (first load)...", end=" ", flush=True)
    start = time.time()
    try:
        from bridge.nemo_server import _get_summarizer
        model = _get_summarizer()
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['distilbart_first_load'] = elapsed
    except Exception as e:
        logger.info(f"SKIP")
        results['distilbart_first_load'] = None
    
    # sentence-transformers (first load)
    logger.info("  • sentence-transformers (first load)...", end=" ", flush=True)
    start = time.time()
    try:
        from core.service.intent_matcher import IntentMatcher
        matcher = IntentMatcher()
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['intent_matcher_first_load'] = elapsed
    except Exception as e:
        logger.info(f"SKIP")
        results['intent_matcher_first_load'] = None
    
    return results


def profile_inference(screenshot_path: str = None):
    """Measure inference latencies."""
    logger.info(f"\n{BLUE}[2/7] Profiling Inference Latencies...{RESET}")
    results = {}
    
    # Create dummy screenshot if needed
    if screenshot_path is None or not Path(screenshot_path).exists():
        logger.info("  • Generating dummy screenshot (1280x720 PNG)...", end=" ", flush=True)
        from PIL import Image
        import io
        
        # Create a simple screenshot with text
        img = Image.new('RGB', (1280, 720), color='white')
        
        # Save to base64
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        screenshot_b64 = base64.b64encode(buf.getvalue()).decode()
        logger.info(f"OK")
    else:
        with open(screenshot_path, 'rb') as f:
            screenshot_b64 = base64.b64encode(f.read()).decode()
    
    # PaddleOCR inference
    logger.info("  • PaddleOCR inference...", end=" ", flush=True)
    start = time.time()
    try:
        from core.vision.omniparser_vision import find_element
        result = find_element(screenshot_b64, "button")
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['paddleocr_inference'] = elapsed
    except Exception as e:
        logger.info(f"SKIP ({str(e)[:30]})")
        results['paddleocr_inference'] = None
    
    # Florence-2 inference
    logger.info("  • Florence-2 inference...", end=" ", flush=True)
    start = time.time()
    try:
        from core.vision.omniparser_vision import find_element_by_description
        result = find_element_by_description(screenshot_b64, "blue button")
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['florence2_inference'] = elapsed
    except Exception as e:
        logger.info(f"SKIP ({str(e)[:30]})")
        results['florence2_inference'] = None
    
    # CLIP inference
    logger.info("  • CLIP inference...", end=" ", flush=True)
    start = time.time()
    try:
        from core.vision.omniparser_vision import detect_screen_state
        result = detect_screen_state(screenshot_b64)
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['clip_inference'] = elapsed
    except Exception as e:
        logger.info(f"SKIP ({str(e)[:30]})")
        results['clip_inference'] = None
    
    # Intent matching
    logger.info("  • Intent matching...", end=" ", flush=True)
    start = time.time()
    try:
        from core.service.intent_matcher import IntentMatcher
        matcher = IntentMatcher()
        intent = matcher.match("search for pizza restaurants", threshold=0.5)
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['intent_matching'] = elapsed
    except Exception as e:
        logger.info(f"SKIP")
        results['intent_matching'] = None
    
    # Summarization
    logger.info("  • Summarization...", end=" ", flush=True)
    start = time.time()
    try:
        from bridge.nemo_server import summarize_text
        text = "This is a test article about artificial intelligence and machine learning. " * 20
        summary = summarize_text(text, max_length=50)
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['summarization'] = elapsed
    except Exception as e:
        logger.info(f"SKIP ({str(e)[:30]})")
        results['summarization'] = None
    
    return results


def profile_full_pipeline(screenshot_path: str = None):
    """Measure full pipeline latency."""
    logger.info(f"\n{BLUE}[3/7] Profiling Full Pipeline...{RESET}")
    results = {}
    
    if screenshot_path is None or not Path(screenshot_path).exists():
        from PIL import Image
        import io
        
        img = Image.new('RGB', (1280, 720), color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        screenshot_b64 = base64.b64encode(buf.getvalue()).decode()
    else:
        with open(screenshot_path, 'rb') as f:
            screenshot_b64 = base64.b64encode(f.read()).decode()
    
    logger.info("  • find_element() (end-to-end)...", end=" ", flush=True)
    start = time.time()
    try:
        from core.vision.omniparser_vision import find_element
        result = find_element(screenshot_b64, "Send Button")
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['find_element_full'] = elapsed
    except Exception as e:
        logger.info(f"SKIP")
        results['find_element_full'] = None
    
    logger.info("  • detect_screen_state() (end-to-end)...", end=" ", flush=True)
    start = time.time()
    try:
        from core.vision.omniparser_vision import detect_screen_state
        result = detect_screen_state(screenshot_b64)
        elapsed = (time.time() - start) * 1000
        logger.info(f"{GREEN}{elapsed:.0f}ms{RESET}")
        results['detect_screen_state_full'] = elapsed
    except Exception as e:
        logger.info(f"SKIP")
        results['detect_screen_state_full'] = None
    
    return results


def get_system_info():
    """Collect system information."""
    logger.info(f"\n{BLUE}[4/7] Collecting System Info...{RESET}")
    
    import torch
    import platform
    
    info = {
        'timestamp': datetime.now().isoformat(),
        'platform': platform.platform(),
        'python_version': platform.python_version(),
        'torch_version': torch.__version__,
        'cuda_available': torch.cuda.is_available(),
        'cuda_device': str(torch.cuda.get_device_name(0)) if torch.cuda.is_available() else None,
        'cuda_memory': f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB" if torch.cuda.is_available() else None,
    }
    
    logger.info(f"  • Platform: {info['platform']}")
    logger.info(f"  • Python: {info['python_version']}")
    logger.info(f"  • PyTorch: {info['torch_version']}")
    logger.info(f"  • CUDA: {info['cuda_available']} ({info['cuda_device']})")
    if info['cuda_memory']:
        logger.info(f"  • GPU Memory: {info['cuda_memory']}")
    
    return info


def analyze_bottlenecks(results):
    """Identify and report bottlenecks."""
    logger.info(f"\n{BLUE}[5/7] Analyzing Bottlenecks...{RESET}")
    
    # Consolidate all timings
    all_times = {}
    for phase in [results.get('model_loading', {}), 
                  results.get('inference', {}),
                  results.get('full_pipeline', {})]:
        all_times.update(phase)
    
    # Filter valid timings
    valid_times = {k: v for k, v in all_times.items() if v is not None}
    
    if not valid_times:
        logger.warning("  • No timing data available")
        return
    
    sorted_times = sorted(valid_times.items(), key=lambda x: x[1], reverse=True)
    
    logger.info(f"  • Top 5 slowest operations:")
    for name, elapsed in sorted_times[:5]:
        logger.info(f"    - {name}: {elapsed:.0f}ms")
    
    # Identify first-load bottlenecks
    first_loads = {k: v for k, v in valid_times.items() if 'first_load' in k}
    if first_loads:
        total_first_load = sum(first_loads.values())
        logger.info(f"  • Total first-load time: {total_first_load:.0f}ms ({len(first_loads)} models)")


def estimate_cached_pipeline():
    """Estimate pipeline performance with full caching."""
    logger.info(f"\n{BLUE}[6/7] Estimating Cached Performance...{RESET}")
    
    logger.info("  • Assumptions:")
    logger.info("    - All models pre-loaded on startup")
    logger.info("    - Element detection results cached by screenshot hash")
    logger.info("    - Intent matches cached by query")
    logger.info("    - Summary cache by text hash (LRU, 100 items)")
    logger.info("  • Expected improvements:")
    logger.info("    - First inference: -50-70% (no model loading)")
    logger.info("    - Repeated queries: -80-95% (cache hits)")
    logger.info("    - Average case: -40-60%")


def main():
    """Run full profiling suite."""
    logger.info(f"\n{YELLOW}╔═══════════════════════════════════════════════════════════╗{RESET}")
    logger.info(f"{YELLOW}║         NEMO Pipeline Latency Profiler - Phase C           ║{RESET}")
    logger.info(f"{YELLOW}╚═══════════════════════════════════════════════════════════╝{RESET}")
    
    results = {
        'system_info': get_system_info(),
        'model_loading': profile_model_loading(),
        'inference': profile_inference(),
        'full_pipeline': profile_full_pipeline(),
    }
    
    # Analyze
    analyze_bottlenecks(results)
    estimate_cached_pipeline()
    
    # Save results
    logger.info(f"\n{BLUE}[7/7] Saving Profile...{RESET}")
    output_file = 'latency_profile.json'
    with open(output_file, 'w') as f:
        # Convert to serializable format
        def serialize(obj):
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            return str(obj)
        
        json.dump(results, f, indent=2, default=serialize)
    
    logger.info(f"  • Saved to: {output_file}")
    
    logger.info(f"\n{GREEN}✓ Profiling complete!{RESET}")
    logger.info(f"  Next: Implement caching and parallel execution")


if __name__ == '__main__':
    main()
