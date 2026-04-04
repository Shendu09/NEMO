"""
Voice Wake Word Listener — Real-time speech recognition for NEMO.

Listens for wake words ("V", "BE", "WE", etc.) and captures voice commands.
Uses faster-whisper for CPU-efficient real-time transcription.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

logger = logging.getLogger("nemo.voice")

# Model will be loaded lazily on first use
_model: Optional[Any] = None
_model_lock = threading.Lock()


def _get_model():
    """Load faster-whisper model (lazy, thread-safe)."""
    global _model
    
    with _model_lock:
        if _model is not None:
            return _model
        
        try:
            logger.info("Loading faster-whisper 'small' model...")
            from faster_whisper import WhisperModel
            
            # Load small model on CPU with int8 quantization
            model = WhisperModel(
                "small",
                device="cpu",
                compute_type="int8",
                num_workers=1,  # Single worker for thread safety
            )
            
            _model = model
            logger.info("✓ Faster-whisper model loaded")
            return model
            
        except ImportError:
            logger.error("faster-whisper not installed. Run: pip install faster-whisper")
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise


def listen_for_wake_word(callback: Callable[[str], None]) -> None:
    """
    Listen for wake words and process voice commands.
    
    Records audio in 2-second chunks, transcribes with faster-whisper,
    detects wake words, and calls callback with extracted command.
    
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
    
    try:
        model = _get_model()
    except Exception as e:
        logger.error(f"Cannot start listener without model: {e}")
        return
    
    logger.info("Voice listener started, waiting for V... command")
    
    # Wake words to detect
    wake_words = {"v", "be", "we", "b", "vi"}
    
    # Audio recording parameters
    sr = 16000  # Sample rate
    duration = 2  # 2-second chunks
    
    try:
        while True:
            try:
                # Record 2-second audio chunk
                logger.debug("Recording audio chunk...")
                audio = sd.rec(
                    int(sr * duration),
                    samplerate=sr,
                    channels=1,
                    dtype=np.float32,
                )
                sd.wait()  # Wait for recording to finish
                
                # Flatten and convert to proper format
                audio_data = audio.flatten()
                
                logger.debug(f"Audio recorded: {len(audio_data)} samples")
                
                # Transcribe with faster-whisper
                logger.debug("Transcribing audio...")
                segments, info = model.transcribe(audio_data, language="en")
                
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
                    logger.debug("No speech detected")
                
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
