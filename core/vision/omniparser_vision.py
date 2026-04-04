"""
OmniParser Vision Module — AI-powered UI element detection.

Provides vision capabilities to NEMO for smart element detection and clicking.
Uses Microsoft's OmniParser model from HuggingFace, with Ollama fallback.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from typing import Any, Optional

import requests
from difflib import SequenceMatcher
from PIL import Image

logger = logging.getLogger("nemo.vision")

# Singleton model instance
_model_instance: Optional[Any] = None
_model_lock = None

try:
    import threading
    _model_lock = threading.Lock()
except ImportError:
    pass


def _get_omniparser_model() -> Optional[Any]:
    """
    Load OmniParser model (singleton pattern).
    
    Attempts to load Microsoft's OmniParser-v2.0 model from HuggingFace.
    Falls back gracefully if model unavailable.
    
    Returns:
        Model instance or None if loading fails
    """
    global _model_instance
    
    if _model_lock:
        _model_lock.acquire()
    
    try:
        if _model_instance is not None:
            return _model_instance
        
        logger.info("Loading OmniParser model from HuggingFace...")
        
        try:
            from transformers import AutoModel, AutoProcessor
            
            # Load processor and model on CPU with float32
            processor = AutoProcessor.from_pretrained(
                "microsoft/OmniParser-v2.0",
                trust_remote_code=True,
            )
            
            model = AutoModel.from_pretrained(
                "microsoft/OmniParser-v2.0",
                trust_remote_code=True,
                device_map="cpu",
                torch_dtype="float32",
            )
            
            # Package both together
            _model_instance = {
                "processor": processor,
                "model": model,
                "available": True,
            }
            
            logger.info("✓ OmniParser model loaded successfully")
            return _model_instance
            
        except Exception as e:
            logger.warning(f"Failed to load OmniParser model: {e}")
            logger.warning("Will fall back to Ollama LLaVA for vision")
            _model_instance = {"available": False}
            return None
            
    finally:
        if _model_lock:
            _model_lock.release()


def _fuzzy_match(target: str, labels: list[str]) -> tuple[str, float]:
    """
    Find best matching label using fuzzy string matching.
    
    Args:
        target: Target label to find
        labels: List of available labels
    
    Returns:
        (best_label, match_score) where score is 0-1
    """
    if not labels:
        return ("", 0.0)
    
    best_label = ""
    best_score = 0.0
    
    target_lower = target.lower()
    
    for label in labels:
        label_lower = label.lower()
        
        # Exact match (highest priority)
        if label_lower == target_lower:
            return (label, 1.0)
        
        # Substring match
        if target_lower in label_lower or label_lower in target_lower:
            score = 0.8
        else:
            # SequenceMatcher ratio
            score = SequenceMatcher(None, target_lower, label_lower).ratio()
        
        if score > best_score:
            best_score = score
            best_label = label
    
    return (best_label, best_score)


def _call_ollama_vision(
    screenshot_b64: str, 
    target: str,
    screen_width: int = 1920,
    screen_height: int = 1080,
) -> dict[str, Any]:
    """
    Fallback to Ollama LLaVA for element detection.
    
    Args:
        screenshot_b64: Base64 encoded screenshot
        target: Target element name to find
        screen_width: Screen width for coordinate scaling
        screen_height: Screen height for coordinate scaling
    
    Returns:
        {found, x, y, label, confidence} dict
    """
    try:
        logger.info(f"Using Ollama LLaVA fallback to find: {target}")
        
        prompt = f"""Find '{target}' in this screenshot. 
        Return ONLY valid JSON (no markdown, no code blocks):
        {{
            "found": true/false,
            "x": pixel_x,
            "y": pixel_y,
            "label": "element_label"
        }}
        
        x,y must be center pixel coordinates of the element."""
        
        # Call Ollama API
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llava",
                "prompt": prompt,
                "images": [screenshot_b64],
                "stream": False,
            },
            timeout=30,
        )
        
        if response.status_code != 200:
            logger.error(f"Ollama returned {response.status_code}")
            return {
                "found": False,
                "x": 0,
                "y": 0,
                "label": "",
                "confidence": 0.0,
            }
        
        # Parse response
        result_text = response.json().get("response", "")
        
        # Extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', result_text)
        if not json_match:
            logger.error("No JSON found in Ollama response")
            return {
                "found": False,
                "x": 0,
                "y": 0,
                "label": "",
                "confidence": 0.0,
            }
        
        json_str = json_match.group(0)
        result = json.loads(json_str)
        
        logger.info(f"Ollama result: {result}")
        
        return {
            "found": result.get("found", False),
            "x": int(result.get("x", 0)),
            "y": int(result.get("y", 0)),
            "label": result.get("label", ""),
            "confidence": 0.7 if result.get("found") else 0.0,
        }
        
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Ollama at localhost:11434")
        return {
            "found": False,
            "x": 0,
            "y": 0,
            "label": "",
            "confidence": 0.0,
        }
    except Exception as e:
        logger.error(f"Ollama vision failed: {e}")
        return {
            "found": False,
            "x": 0,
            "y": 0,
            "label": "",
            "confidence": 0.0,
        }


def find_element(
    screenshot_b64: str,
    target: str,
    screen_width: Optional[int] = None,
    screen_height: Optional[int] = None,
) -> dict[str, Any]:
    """
    Find a UI element by name in a screenshot.
    
    Uses OmniParser to detect UI elements with bounding boxes,
    then fuzzy-matches to find the target. Falls back to Ollama LLaVA
    if OmniParser unavailable.
    
    Args:
        screenshot_b64: Base64 encoded screenshot (PNG)
        target: Target element name (e.g., "Send Button", "Username Field")
        screen_width: Screen width for scaling (auto-detect if None)
        screen_height: Screen height for scaling (auto-detect if None)
    
    Returns:
        {
            "found": bool,
            "x": int (center pixel x),
            "y": int (center pixel y),
            "label": str (actual element label),
            "confidence": float (0-1),
        }
    """
    try:
        logger.debug(f"Finding element: {target}")
        
        # Decode screenshot
        try:
            img_data = base64.b64decode(screenshot_b64)
            image = Image.open(io.BytesIO(img_data))
            image = image.convert("RGB")
        except Exception as e:
            logger.error(f"Failed to decode screenshot: {e}")
            return {
                "found": False,
                "x": 0,
                "y": 0,
                "label": "",
                "confidence": 0.0,
            }
        
        # Auto-detect screen dimensions if not provided
        if screen_width is None:
            screen_width = image.width
        if screen_height is None:
            screen_height = image.height
        
        logger.debug(f"Screenshot size: {image.width}x{image.height}, "
                    f"Screen size: {screen_width}x{screen_height}")
        
        # Try OmniParser first
        model_data = _get_omniparser_model()
        
        if model_data and model_data.get("available"):
            try:
                logger.debug("Using OmniParser for element detection")
                processor = model_data["processor"]
                model = model_data["model"]
                
                # Prepare input
                inputs = processor(image, return_tensors="pt")
                
                # Run inference
                with __import__('torch').no_grad():
                    outputs = model(**inputs)
                
                # Extract detections
                # OmniParser returns detections in format:
                # Each detection has: bbox [x1, y1, x2, y2], label, confidence
                detections = outputs.get("detections", [])
                
                if not detections:
                    logger.warning("OmniParser found no elements")
                    # Fall back to Ollama
                    return _call_ollama_vision(
                        screenshot_b64, target, screen_width, screen_height
                    )
                
                # Extract labels and bounding boxes
                labels = []
                bboxes = []  # [[x1, y1, x2, y2], ...]
                confidences = []
                
                for det in detections:
                    bbox = det.get("bbox", [0, 0, 1, 1])  # normalized 0-1
                    label = det.get("label", "")
                    conf = det.get("confidence", 0.0)
                    
                    labels.append(label)
                    bboxes.append(bbox)
                    confidences.append(conf)
                
                logger.debug(f"OmniParser detected {len(labels)} elements: {labels}")
                
                # Fuzzy match target
                matched_label, match_score = _fuzzy_match(target, labels)
                
                if match_score < 0.3:  # Low confidence match
                    logger.warning(f"Low match confidence: {match_score}")
                    return {
                        "found": False,
                        "x": 0,
                        "y": 0,
                        "label": matched_label,
                        "confidence": match_score,
                    }
                
                # Find index of matched label
                matched_idx = labels.index(matched_label)
                bbox = bboxes[matched_idx]  # [x1, y1, x2, y2] in 0-1 range
                bbox_conf = confidences[matched_idx]
                
                # Scale bbox from 0-1 to actual screen pixels
                x1 = int(bbox[0] * screen_width)
                y1 = int(bbox[1] * screen_height)
                x2 = int(bbox[2] * screen_width)
                y2 = int(bbox[3] * screen_height)
                
                # Calculate center
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                logger.info(f"Found '{matched_label}' at ({center_x}, {center_y}), "
                           f"confidence: {bbox_conf:.2f}")
                
                return {
                    "found": True,
                    "x": center_x,
                    "y": center_y,
                    "label": matched_label,
                    "confidence": min(bbox_conf, match_score),
                }
                
            except Exception as e:
                logger.warning(f"OmniParser inference failed: {e}")
                logger.info("Falling back to Ollama LLaVA")
                return _call_ollama_vision(
                    screenshot_b64, target, screen_width, screen_height
                )
        
        # OmniParser not available, use Ollama
        logger.debug("OmniParser not available, using Ollama LLaVA")
        return _call_ollama_vision(
            screenshot_b64, target, screen_width, screen_height
        )
        
    except Exception as e:
        logger.error(f"find_element failed: {e}")
        return {
            "found": False,
            "x": 0,
            "y": 0,
            "label": "",
            "confidence": 0.0,
        }


def list_elements(
    screenshot_b64: str,
    screen_width: Optional[int] = None,
    screen_height: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    List all detected UI elements in a screenshot.
    
    Args:
        screenshot_b64: Base64 encoded screenshot (PNG)
        screen_width: Screen width for scaling (auto-detect if None)
        screen_height: Screen height for scaling (auto-detect if None)
    
    Returns:
        List of dicts: [{label, x, y, width, height, confidence}, ...]
        x, y are center coordinates in screen pixels
    """
    try:
        logger.debug("Listing all elements in screenshot")
        
        # Decode screenshot
        try:
            img_data = base64.b64decode(screenshot_b64)
            image = Image.open(io.BytesIO(img_data))
            image = image.convert("RGB")
        except Exception as e:
            logger.error(f"Failed to decode screenshot: {e}")
            return []
        
        # Auto-detect screen dimensions if not provided
        if screen_width is None:
            screen_width = image.width
        if screen_height is None:
            screen_height = image.height
        
        logger.debug(f"Screenshot: {image.width}x{image.height}, "
                    f"Screen: {screen_width}x{screen_height}")
        
        # Try OmniParser
        model_data = _get_omniparser_model()
        
        if model_data and model_data.get("available"):
            try:
                logger.debug("Using OmniParser to list elements")
                processor = model_data["processor"]
                model = model_data["model"]
                
                # Prepare input
                inputs = processor(image, return_tensors="pt")
                
                # Run inference
                with __import__('torch').no_grad():
                    outputs = model(**inputs)
                
                # Extract detections
                detections = outputs.get("detections", [])
                
                elements = []
                for det in detections:
                    bbox = det.get("bbox", [0, 0, 1, 1])  # normalized
                    label = det.get("label", "")
                    conf = det.get("confidence", 0.0)
                    
                    # Scale to screen pixels
                    x1 = int(bbox[0] * screen_width)
                    y1 = int(bbox[1] * screen_height)
                    x2 = int(bbox[2] * screen_width)
                    y2 = int(bbox[3] * screen_height)
                    
                    width = x2 - x1
                    height = y2 - y1
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    
                    elements.append({
                        "label": label,
                        "x": center_x,
                        "y": center_y,
                        "width": width,
                        "height": height,
                        "confidence": conf,
                    })
                
                logger.info(f"Listed {len(elements)} elements")
                return elements
                
            except Exception as e:
                logger.error(f"OmniParser list failed: {e}")
                return []
        
        logger.warning("OmniParser not available, cannot list elements")
        return []
        
    except Exception as e:
        logger.error(f"list_elements failed: {e}")
        return []


class VisionProvider:
    """
    High-level vision API for NEMO-OS.
    
    Provides a class-based interface for vision operations.
    """
    
    @staticmethod
    def find(screenshot_b64: str, target: str) -> dict[str, Any]:
        """Find an element in a screenshot."""
        return find_element(screenshot_b64, target)
    
    @staticmethod
    def list_all(screenshot_b64: str) -> list[dict[str, Any]]:
        """List all elements in a screenshot."""
        return list_elements(screenshot_b64)
