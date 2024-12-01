from .videoRecorder import RecorderUI, ScreenRecorder
from .audio_recorder import AudioRecorderManager

__version__ = "0.1.1"

def main():
    """Entry point for the application"""
    ui = RecorderUI()
    ui.run()

__all__ = ['RecorderUI', 'ScreenRecorder', 'AudioRecorderManager', 'main'] 