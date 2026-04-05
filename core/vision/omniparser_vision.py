"""
EasyOCR + CLIP Vision Module — Neural network-powered UI element detection.

Provides vision capabilities using:
- EasyOCR: Optical character recognition for text detection
- CLIP: Vision-language model for screen state understanding
- Ollama LLaVA: Fallback LLM reasoning

All models are lazily loaded to prevent server startup crashes.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import threading
from typing import Any, Optional

import requests
from difflib import SequenceMatcher
from PIL import Image

logger = logging.getLogger("nemo.vision")

# Singleton model instances (lazy-loaded)
_easyocr_reader: Optional[Any] = None
_clip_model: Optional[Any] = None
_clip_processor: Optional[Any] = None
_models_lock = threading.Lock()


def _get_easyocr_reader() -> Optional[Any]:
    """Load EasyOCR reader (singleton, lazy-loaded on first use)."""
    global _easyocr_reader
    
    if _easyocr_reader is not None:
        return _easyocr_reader
    
    with _models_lock:
        if _easyocr_reader is not None:
            return _easyocr_reader
        
        try:
            logger.info("Loading EasyOCR... (first run may take 1-2 minutes)")
            import easyocr
            _easyocr_reader = easyocr.Reader(
                ["en"],
                gpu=False,
                model_storage_directory=None,
                user_network_directory=None,
                recog_network="standard",
                download_enabled=True,
            )
            logger.info("✓ EasyOCR loaded successfully")
            return _easyocr_reader
        except Exception as e:
            logger.warning(f"Failed to load EasyOCR: {e}")
            return None


def _get_clip_model() -> Optional[tuple[Any, Any]]:
    """Load CLIP model and processor (singleton, lazy-loaded)."""
    global _clip_model, _clip_processor
    
    if _clip_model is not None and _clip_processor is not None:
        return (_clip_model, _clip_processor)
    
    with _models_lock:
        if _clip_model is not None and _clip_processor is not None:
            return (_clip_model, _clip_processor)
        
        try:
            logger.info("Loading CLIP model... (first run may download ~350MB)")
            import open_clip
            import torch
            
            _clip_model, _, _clip_processor = open_clip.create_model_and_transforms(
                "ViT-B-32",
                pretrained="openai",
                device="cpu",
            )
            logger.info("✓ CLIP model loaded successfully")
            return (_clip_model, _clip_processor)
        except Exception as e:
            logger.warning(f"Failed to load CLIP: {e}")
            return None


def _fuzzy_match(target: str, labels: list[str]) -> tuple[str, float]:
    """
    Find best matching label using fuzzy string matching.
    Returns (best_label, match_score) where score is 0-1.
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
    """Fallback to Ollama LLaVA for element detection."""
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
        
        result_text = response.json().get("response", "")
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
    
    Uses EasyOCR to detect text on screen, then fuzzy-matches to find
    the target element. Falls back to Ollama LLaVA if EasyOCR unavailable.
    
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
        
        # Try EasyOCR first
        reader = _get_easyocr_reader()
        
        if reader is not None:
            try:
                logger.debug("Using EasyOCR for element detection")
                import numpy as np
                
                # Convert PIL to numpy for EasyOCR
                img_np = np.array(image)
                
                # Run OCR
                results = reader.readtext(img_np, detail=1)
                
                if not results:
                    logger.warning("EasyOCR found no text")
                    return _call_ollama_vision(
                        screenshot_b64, target, screen_width, screen_height
                    )
                
                # Extract text and bounding boxes
                labels = []
                bboxes = []  # [[(x1,y1), (x2,y2), (x3,y3), (x4,y4)], ...]
                confidences = []
                
                for (bbox, text, conf) in results:
                    labels.append(text.strip())
                    bboxes.append(bbox)  # List of corner points
                    confidences.append(conf)
                
                logger.debug(f"EasyOCR detected {len(labels)} text regions: {labels}")
                
                # Fuzzy match target
                matched_label, match_score = _fuzzy_match(target, labels)
                
                if match_score < 0.3:  # Low confidence match
                    logger.warning(f"Low match confidence: {match_score}")
                    return _call_ollama_vision(
                        screenshot_b64, target, screen_width, screen_height
                    )
                
                # Find index of matched label
                matched_idx = labels.index(matched_label)
                bbox = bboxes[matched_idx]  # Corner points
                bbox_conf = confidences[matched_idx]
                
                # Calculate center from corner points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                xs = [pt[0] for pt in bbox]
                ys = [pt[1] for pt in bbox]
                center_x = int(sum(xs) / len(xs))
                center_y = int(sum(ys) / len(ys))
                
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
                logger.warning(f"EasyOCR inference failed: {e}")
                logger.info("Falling back to Ollama LLaVA")
                return _call_ollama_vision(
                    screenshot_b64, target, screen_width, screen_height
                )
        
        # EasyOCR not available, use Ollama
        logger.debug("EasyOCR not available, using Ollama LLaVA")
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
        
        # Try EasyOCR
        reader = _get_easyocr_reader()
        
        if reader is not None:
            try:
                logger.debug("Using EasyOCR to list elements")
                import numpy as np
                
                # Convert PIL to numpy for EasyOCR
                img_np = np.array(image)
                
                # Run OCR
                results = reader.readtext(img_np, detail=1)
                
                elements = []
                for (bbox, text, conf) in results:
                    text = text.strip()
                    if not text:
                        continue
                    
                    # Calculate center and dimensions from corner points
                    xs = [pt[0] for pt in bbox]
                    ys = [pt[1] for pt in bbox]
                    x1, x2 = min(xs), max(xs)
                    y1, y2 = min(ys), max(ys)
                    
                    width = x2 - x1
                    height = y2 - y1
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    
                    elements.append({
                        "label": text,
                        "x": center_x,
                        "y": center_y,
                        "width": width,
                        "height": height,
                        "confidence": conf,
                    })
                
                logger.info(f"Listed {len(elements)} elements")
                return elements
                
            except Exception as e:
                logger.error(f"EasyOCR list failed: {e}")
                return []
        
        logger.warning("EasyOCR not available, cannot list elements")
        return []
        
    except Exception as e:
        logger.error(f"list_elements failed: {e}")
        return []


def detect_screen_state(screenshot_b64: str) -> dict[str, Any]:
    """
    Detect high-level screen state using CLIP vision-language model.
    
    Returns semantic understanding of what's on screen:
    - is_chrome: Likely a Chrome browser window
    - is_settings: Likely a settings/preferences screen
    - is_login: Likely a login form
    - is_profile_picker: Likely Chrome profile picker
    - primary_app: Detected application (chrome, edge, whatsapp, etc.)
    
    Args:
        screenshot_b64: Base64 encoded screenshot (PNG)
    
    Returns:
        {
            "is_chrome": bool,
            "is_settings": bool,
            "is_login": bool,
            "is_profile_picker": bool,
            "primary_app": str,
            "confidence": float (0-1),
        }
    """
    try:
        logger.debug("Detecting screen state with CLIP")
        
        # Decode screenshot
        try:
            img_data = base64.b64decode(screenshot_b64)
            image = Image.open(io.BytesIO(img_data))
            image = image.convert("RGB")
        except Exception as e:
            logger.error(f"Failed to decode screenshot: {e}")
            return {
                "is_chrome": False,
                "is_settings": False,
                "is_login": False,
                "is_profile_picker": False,
                "primary_app": "unknown",
                "confidence": 0.0,
            }
        
        # Try CLIP model
        clip_data = _get_clip_model()
        
        if clip_data is not None:
            try:
                import torch
                model, processor = clip_data
                
                logger.debug("Using CLIP for screen state detection")
                
                # Prepare image
                image_input = processor(image).unsqueeze(0)
                
                # Text prompts to classify
                prompts = [
                    "This is a Chrome browser window",
                    "This is a Firefox browser window",
                    "This is Microsoft Edge browser window",
                    "This is a Chrome profile selection screen",
                    "This is a login or authentication screen",
                    "This is a settings or preferences screen",
                    "This is WhatsApp application",
                    "This is a desktop or home screen",
                ]
                
                text_tokens = torch.cat([
                    processor.tokenize(p) for p in prompts
                ]).unsqueeze(0)
                
                with torch.no_grad():
                    image_features = model.encode_image(image_input)
                    text_features = model.encode_text(text_tokens)
                    
                    # Normalize
                    image_features /= image_features.norm(dim=-1, keepdim=True)
                    text_features /= text_features.norm(dim=-1, keepdim=True)
                    
                    # Compute similarity
                    similarity = (image_features @ text_features.T).squeeze(0)
                
                # Get scores for each classification
                is_chrome = similarity[0].item() > 0.25
                is_firefox = similarity[1].item() > 0.25
                is_edge = similarity[2].item() > 0.25
                is_profile_picker = similarity[3].item() > 0.25
                is_login = similarity[4].item() > 0.25
                is_settings = similarity[5].item() > 0.25
                is_whatsapp = similarity[6].item() > 0.25
                
                # Determine primary app
                if is_chrome:
                    primary_app = "chrome"
                elif is_firefox:
                    primary_app = "firefox"
                elif is_edge:
                    primary_app = "edge"
                elif is_whatsapp:
                    primary_app = "whatsapp"
                else:
                    primary_app = "unknown"
                
                # Confidence is max similarity
                confidence = max(similarity).item()
                
                logger.info(f"Screen state: app={primary_app}, "
                           f"chrome={is_chrome}, profile_picker={is_profile_picker}, "
                           f"login={is_login}, confidence={confidence:.2f}")
                
                return {
                    "is_chrome": is_chrome,
                    "is_settings": is_settings,
                    "is_login": is_login,
                    "is_profile_picker": is_profile_picker,
                    "primary_app": primary_app,
                    "confidence": confidence,
                }
                
            except Exception as e:
                logger.warning(f"CLIP inference failed: {e}")
                return {
                    "is_chrome": False,
                    "is_settings": False,
                    "is_login": False,
                    "is_profile_picker": False,
                    "primary_app": "unknown",
                    "confidence": 0.0,
                }
        
        logger.warning("CLIP not available, cannot detect screen state")
        return {
            "is_chrome": False,
            "is_settings": False,
            "is_login": False,
            "is_profile_picker": False,
            "primary_app": "unknown",
            "confidence": 0.0,
        }
        
    except Exception as e:
        logger.error(f"detect_screen_state failed: {e}")
        return {
            "is_chrome": False,
            "is_settings": False,
            "is_login": False,
            "is_profile_picker": False,
            "primary_app": "unknown",
            "confidence": 0.0,
        }


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
    
    @staticmethod
    def detect_state(screenshot_b64: str) -> dict[str, Any]:
        """Detect screen state (app, login screen, profile picker, etc.)."""
        return detect_screen_state(screenshot_b64)
