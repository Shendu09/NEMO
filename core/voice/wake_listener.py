"""
Voice Wake Word Listener — Real-time speech recognition for NEMO.

Listens for wake words ("V", "BE", "WE", etc.) and captures voice commands.
Uses Silero VAD for CPU-efficient voice activity detection.
Uses faster-whisper for transcription only when speech is detected.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

# GPU Setup: CUDA detection for faster-whisper
import torch
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

logger = logging.getLogger("nemo.voice")

# Models will be loaded lazily on first use
_vad_model: Optional[Any] = None
_whisper_model: Optional[Any] = None
_models_lock = threading.Lock()


def _get_vad_model() -> Optional[Any]:
    """Load Silero VAD model (lazy, thread-safe)."""
    global _vad_model
    
    if _vad_model is not None:
        return _vad_model
    
    with _models_lock:
        if _vad_model is not None:
            return _vad_model
        
        try:
            logger.info("Loading Silero VAD model...")
            import torch
            
            # Load pretrained Silero VAD
            vad = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=True,
            )
            
            _vad_model = vad
            logger.info("✓ Silero VAD model loaded")
            return vad
            
        except Exception as e:
            logger.warning(f"Failed to load Silero VAD: {e}")
            logger.warning("Will transcribe all audio chunks (less efficient)")
            return None


def _get_whisper_model() -> Optional[Any]:
    """Load faster-whisper model (lazy, thread-safe).
    
    Uses CUDA GPU if available (float16 for speed), falls back to CPU with int8 quantization.
    """
    global _whisper_model
    
    if _whisper_model is not None:
        return _whisper_model
    
    with _models_lock:
        if _whisper_model is not None:
            return _whisper_model
        
        try:
            logger.info("Loading faster-whisper 'small' model...")
            from faster_whisper import WhisperModel
            
            # Use GPU if available
            if DEVICE == "cuda":
                logger.info("Loading faster-whisper on CUDA (float16 precision)...")
                model = WhisperModel(
                    "small",
                    device="cuda",
                    compute_type="float16",
                    num_workers=1,
                )
            else:
                logger.info("Loading faster-whisper on CPU (int8 quantization)...")
                model = WhisperModel(
                    "small",
                    device="cpu",
                    compute_type="int8",
                    num_workers=1,
                )
            
            _whisper_model = model
            logger.info(f"✓ Faster-whisper model loaded on {DEVICE}")
            return model
            
        except ImportError:
            logger.error("faster-whisper not installed. Run: pip install faster-whisper")
            return None
        except Exception as e:
            logger.error(f"Failed to load whisper model: {e}")
            return None


def _detect_speech(audio_chunk: Any, vad_model: Any, sr: int = 16000) -> bool:
    """
    Detect if audio chunk contains speech using Silero VAD.
    
    Args:
        audio_chunk: Audio numpy array (mono, 16000 Hz)
        vad_model: Loaded Silero VAD model
        sr: Sample rate (default 16000 Hz)
    
    Returns:
        True if speech detected, False otherwise
    """
    try:
        import torch
        
        # Convert to torch tensor
        if not isinstance(audio_chunk, torch.Tensor):
            audio_chunk = torch.from_numpy(audio_chunk).float()
        
        # Ensure correct shape and length
        if audio_chunk.dim() > 1:
            audio_chunk = audio_chunk.squeeze()
        
        # Silero VAD expects 16000 Hz audio
        if sr != 16000:
            import torchaudio
            audio_chunk = torchaudio.functional.resample(
                audio_chunk, orig_freq=sr, new_freq=16000
            )
        
        # Run VAD
        with torch.inference_mode():
            pred = vad_model(audio_chunk, 16000)
        
        # pred is probability of speech (0-1)
        speech_detected = pred > 0.5
        
        logger.debug(f"VAD confidence: {pred:.2f}, speech detected: {speech_detected}")
        return bool(speech_detected)
        
    except Exception as e:
        logger.warning(f"VAD inference failed: {e}, transcribing anyway")
        return True  # Default to transcribing if VAD fails


def listen_for_wake_word(callback: Callable[[str], None]) -> None:
    """
    Listen for wake words and process voice commands.
    
    Records audio in 1-second chunks. For each chunk:
    1. Detects speech using Silero VAD (CPU-efficient)
    2. If speech detected, transcribes with faster-whisper
    3. Looks for wake word and calls callback with command
    
    Wake words: "V", "BE", "WE", "B", "VI" (case-insensitive)
    
    Args:
        callback: Function to call with extracted command.
                 Will be called in a daemon thread.
    """
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        logger.error("sounddevice not installed. Run: pip install sounddevice numpy")
        return
    
    # Load models
    vad_model = _get_vad_model()
    whisper_model = _get_whisper_model()
    
    if whisper_model is None:
        logger.error("Cannot start listener without whisper model")
        return
    
    logger.info("Voice listener started, waiting for V... command")
    
    # Wake words to detect
    wake_words = {"v", "be", "we", "b", "vi"}
    
    # Audio recording parameters
    sr = 16000  # Sample rate
    duration = 1  # 1-second chunks (VAD is more efficient with shorter windows)
    
    try:
        while True:
            try:
                # Record 1-second audio chunk
                logger.debug("Recording audio...")
                audio = sd.rec(
                    int(sr * duration),
                    samplerate=sr,
                    channels=1,
                    dtype=np.float32,
                )
                sd.wait()  # Wait for recording to finish
                
                # Flatten
                audio_data = audio.flatten()
                
                # Check for speech using Silero VAD
                speech_detected = False
                if vad_model is not None:
                    speech_detected = _detect_speech(audio_data, vad_model, sr)
                else:
                    # If VAD unavailable, check if audio has significant energy
                    import numpy as np
                    rms = np.sqrt(np.mean(audio_data ** 2))
                    speech_detected = rms > 0.01  # Threshold for voice
                    logger.debug(f"RMS energy: {rms:.4f}, speech detected: {speech_detected}")
                
                if not speech_detected:
                    logger.debug("No speech detected, skipping transcription")
                    logger.info("Listening for V...")
                    continue
                
                logger.debug("Speech detected, transcribing...")
                
                # Transcribe with faster-whisper only if speech detected
                segments, info = whisper_model.transcribe(
                    audio_data,
                    language="en",
                    condition_on_previous_text=False,
                )
                
                # Convert segments to text
                transcription = " ".join(segment.text for segment in segments)
                
                if transcription.strip():
                    logger.debug(f"Transcription: {transcription}")
                    
                    # Split into words and check for wake word
                    words = transcription.lower().split()
                    
                    if words and words[0] in wake_words:
                        # Extract command (everything after first word)
                        command = " ".join(words[1:]).strip()
                        
                        # Skip empty commands or "never mind"
                        if command and command != "never mind":
                            logger.info(f"[V] Command: {command}")
                            
                            # Call callback in daemon thread
                            thread = threading.Thread(
                                target=callback,
                                args=(command,),
                                daemon=True,
                            )
                            thread.start()
                        elif not command:
                            logger.debug("Empty command, skipping")
                        else:
                            logger.info("Cancelled (never mind)")
                else:
                    logger.debug("No speech content after transcription")
                
                logger.info("Listening for V...")
                
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                logger.info("Listening for V...")
                continue
    
    except KeyboardInterrupt:
        logger.info("Voice listener stopped")
    except Exception as e:
        logger.error(f"Fatal error in voice listener: {e}")


def start(callback: Callable[[str], None]) -> None:
    """
    Start voice wake word listener in background.
    
    Launches listen_for_wake_word in a daemon thread so it runs
    in the background without blocking the main program.
    
    Args:
        callback: Function to call when wake word + command detected.
    """
    logger.info("Starting voice listener daemon...")
    
    thread = threading.Thread(
        target=listen_for_wake_word,
        args=(callback,),
        daemon=True,
    )
    thread.start()
    
    logger.info("Voice listener daemon started")
