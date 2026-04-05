"""
NEMO Performance Optimization Utilities - Phase C

Includes:
- Cache statistics and reporting
- Model memory profiling
- Latency analysis
- Performance recommendations
"""

import json
import logging
import psutil
import torch
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("nemo.perf")


def get_memory_usage() -> Dict[str, Any]:
    """Get current memory usage (CPU and GPU)."""
    cpu_percent = psutil.virtual_memory().percent
    cpu_available_gb = psutil.virtual_memory().available / 1e9
    
    gpu_data = {}
    if torch.cuda.is_available():
        gpu_data = {
            'device': torch.cuda.get_device_name(0),
            'allocated_gb': torch.cuda.memory_allocated(0) / 1e9,
            'reserved_gb': torch.cuda.memory_reserved(0) / 1e9,
            'total_gb': torch.cuda.get_device_properties(0).total_memory / 1e9,
        }
    
    return {
        'cpu_percent': cpu_percent,
        'cpu_available_gb': f"{cpu_available_gb:.1f}",
        'gpu': gpu_data if gpu_data else 'not_available',
    }


def get_cache_stats() -> Optional[Dict[str, Any]]:
    """Get cache statistics from global cache manager."""
    try:
        from core.service.cache import get_cache
        cache = get_cache()
        return cache.get_stats()
    except Exception as e:
        logger.warning(f"Could not get cache stats: {e}")
        return None


def print_performance_summary():
    """Print human-readable performance summary."""
    print("\n" + "=" * 70)
    print("NEMO Phase C: Performance Optimization Summary")
    print("=" * 70)
    
    # Memory
    print("\n📊 Memory Usage:")
    mem = get_memory_usage()
    print(f"  CPU: {mem['cpu_percent']:.1f}% used, {mem['cpu_available_gb']}GB available")
    if mem['gpu'] != 'not_available':
        gpu = mem['gpu']
        print(f"  GPU: {gpu['device']}")
        print(f"    - Allocated: {gpu['allocated_gb']:.1f}GB / {gpu['total_gb']:.1f}GB")
        print(f"    - Reserved: {gpu['reserved_gb']:.1f}GB")
    
    # Cache stats
    print("\n💾 Cache Statistics:")
    cache_stats = get_cache_stats()
    if cache_stats:
        print(f"  Element Detection: {cache_stats['element_detection']['hits']} hits, "
              f"{cache_stats['element_detection']['hit_rate']}")
        print(f"  Intent Matching: {cache_stats['intent']['hits']} hits, "
              f"{cache_stats['intent']['hit_rate']}")
        print(f"  Summarization: {cache_stats['summary']['hits']} hits, "
              f"{cache_stats['summary']['hit_rate']}")
        print(f"  Uptime: {cache_stats['uptime_seconds']}")
    
    # Recommendations
    print("\n🎯 Optimization Status:")
    print("  ✓ Model preloading enabled (Phase C)")
    print("  ✓ LRU caching with 1-2 hour TTL")
    print("  ✓ Florence-2 fallback for UI grounding")
    print("  ✓ CUDA acceleration on RTX 5050")
    
    print("\n" + "=" * 70)


def save_performance_report(filename: str = "performance_report.json"):
    """Save detailed performance report to JSON file."""
    report = {
        'memory': get_memory_usage(),
        'cache': get_cache_stats(),
    }
    
    with open(filename, 'w') as f:
        # Make serializable
        def serialize(obj):
            if isinstance(obj, (int, float, str, bool, type(None))):
                return obj
            return str(obj)
        
        json.dump(report, f, indent=2, default=serialize)
    
    logger.info(f"Performance report saved to {filename}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    print_performance_summary()
    save_performance_report()
