# RecMaster Screen Recorder

RecMaster is a simple & smooth screen recording tool built with Python, featuring system audio capture and multi-monitor support. It leverages Windows native APIs for optimal performance and reliability.

## Features

- **Multi-Monitor Support**: Record from any monitor or selected screen area
- **System Audio Capture**: Record system audio output (WASAPI loopback)
- **Multiple Audio Sources**: Support for both output (speakers/headphones) and input (microphone) devices
- **High Quality**: Configurable video quality settings from low to ultra-high
- **Real-time Preview**: Live recording border and status display
- **Flexible Output**: MP4 video format with AAC audio encoding


## 安装

```bash
pip install RecMaster
```


## Technical Architecture

### Core Components

1. **Video Capture**
   - Uses `ffmpeg` for screen capture via GDI
   - Direct hardware acceleration support
   - Real-time encoding with libx264
   - Custom quality presets with configurable parameters

2. **Audio Capture**
   - Windows Core Audio APIs (WASAPI)
   - COM-based device enumeration
   - Real-time audio device monitoring
   - Multiple device simultaneous recording

3. **UI Layer**
   - Tkinter-based user interface
   - Multi-threaded design for responsive UI
   - Real-time status updates
   - DPI-aware window management

### Audio Technology Stack

#### WASAPI Integration
The recorder uses Windows Audio Session API (WASAPI) for high-quality audio capture:
- Direct access to audio endpoints
- Loopback recording for system sounds
- Exclusive mode support
- Low-latency audio capture

#### Audio Format Specifications
- Sample Rate: 44.1 kHz (default)
- Bit Depth: 32-bit float (capture) / 16-bit PCM (storage)
- Channels: Stereo (2 channels)
- Buffer Size: 10ms chunks
- Format: IEEE float (internal) / PCM (output)

#### Device Management
- Real-time device enumeration
- Default device detection
- Hot-plug device support
- Multiple device simultaneous recording

### Video Technology Stack

#### Screen Capture
- GDI-based capture through ffmpeg
- Hardware-accelerated encoding
- Custom region selection
- Multi-monitor awareness

#### Quality Presets
```python
Quality Settings:
1 (Lowest):   15fps, CRF 32, ultrafast preset, 1000k bitrate
2 (Low):      20fps, CRF 28, veryfast preset, 1500k bitrate
3 (Medium):   24fps, CRF 23, medium preset,   2500k bitrate
4 (High):     30fps, CRF 20, slow preset,     4000k bitrate
5 (Ultra):    60fps, CRF 18, veryslow preset, 6000k bitrate
```

### Audio-Video Synchronization

#### Timing Mechanism
- Precise timestamps for both audio and video streams
- Buffer management for audio samples
- Frame-accurate synchronization
- Silent frame insertion for continuous audio

#### Buffer Management
- Audio buffer size: 10ms chunks
- Real-time buffer statistics monitoring
- Empty packet detection and handling
- Automatic buffer underrun compensation

## Dependencies

### Core Dependencies
```
comtypes
numpy
pywin32
pycaw
ffmpeg-python
humanize
```

### System Requirements
- Windows 7 or later
- DirectX 9 or later
- FFmpeg installed and in system PATH
- Python 3.7 or later

### Windows API Dependencies
- User32.dll
- Kernel32.dll
- Ole32.dll
- MMDevAPI.dll

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install FFmpeg:
```bash
# Using chocolatey
choco install ffmpeg

# Or download from ffmpeg.org and add to PATH
```

3. Run the recorder:
```bash
python videoRecorder.py
```

## Development Details

### Audio Recording Implementation

The audio recording system uses a complex buffer management system:

#### WASAPI Client Implementation
```python
# Audio client initialization with specific format
wave_format = WAVEFORMATEX(
    wFormatTag=WAVE_FORMAT_IEEE_FLOAT,
    nChannels=2,
    nSamplesPerSec=44100,
    wBitsPerSample=32,
    nBlockAlign=8,
    nAvgBytesPerSec=352800,
    cbSize=0
)
```

#### Buffer Processing
- **Chunk Size**: 10ms of audio data (441 samples at 44.1kHz)
- **Format Conversion**: 32-bit float to 16-bit PCM
- **Silent Frame Insertion**: Maintains audio continuity during inactive periods
- **Activity Detection**: Monitors audio levels to optimize storage

#### Audio Device Management
1. **Device Enumeration**
   - Uses COM interfaces for device discovery
   - Supports hot-plug detection
   - Automatic default device selection
   - Multiple device simultaneous recording

2. **Device Initialization**
   ```python
   # Example device initialization flow
   enumerator = CoCreateInstance(CLSID_MMDeviceEnumerator)
   device = enumerator.GetDefaultAudioEndpoint()
   audio_client = device.Activate(IAudioClient)
   ```

3. **Format Negotiation**
   - Automatic format detection
   - Sample rate adaptation
   - Channel count matching
   - Bit depth optimization

### Video Recording Implementation

#### FFmpeg Integration
```bash
ffmpeg -f gdigrab -framerate {fps} -offset_x {x} -offset_y {y} \
       -video_size {width}x{height} -draw_mouse 1 -i desktop \
       -c:v libx264 -preset {preset} -crf {crf} -b:v {bitrate} \
       -pix_fmt yuv420p output.mp4
```

#### Screen Capture Features
1. **Region Selection**
   - Multi-monitor coordinate system
   - DPI-aware positioning
   - Real-time border preview
   - Drag-and-drop selection

2. **Performance Optimization**
   - Hardware-accelerated encoding
   - Adaptive quality settings
   - Memory usage optimization
   - CPU load balancing

### Synchronization Implementation

#### Time Management
```python
# Timestamp synchronization example
video_start_time = time.time()
audio_start_time = time.time()

# Offset calculation
sync_offset = audio_start_time - video_start_time
```

#### Buffer Synchronization
1. **Audio Buffer Management**
   - Real-time statistics tracking
   - Buffer underrun detection
   - Automatic compensation
   - Performance monitoring

2. **Video Frame Alignment**
   - Frame rate maintenance
   - Timestamp verification
   - Drop frame handling
   - Delay compensation

### Error Handling and Recovery

#### Audio Stream Recovery
```python
def handle_audio_error(self):
    try:
        # Attempt to recover audio stream
        self.reinitialize_audio_client()
        self.insert_silence_frames()
    except Exception as e:
        self.fallback_to_video_only()
```

#### Common Issues and Solutions

1. **Audio Device Issues**
   - Device disconnection handling
   - Format mismatch recovery
   - Buffer overflow protection
   - Stream restoration

2. **Video Capture Issues**
   - Region boundary validation
   - Monitor resolution changes
   - DPI scaling adjustments
   - Resource cleanup

### Performance Considerations

#### Memory Management
- Efficient buffer allocation
- Periodic garbage collection
- Resource pooling
- Memory leak prevention

#### CPU Utilization
- Thread priority management
- Workload distribution
- Process affinity settings
- Background task optimization

### Development Guidelines

#### Adding New Features
1. **Audio Device Support**
   ```python
   def add_audio_device(self):
       """
       Template for adding new audio device support
       """
       # Device initialization
       # Format negotiation
       # Buffer setup
       # Error handling
   ```

2. **Video Format Support**
   ```python
   def add_video_format(self):
       """
       Template for adding new video format support
       """
       # Format validation
       # FFmpeg parameter adjustment
       # Quality preset definition
       # Performance testing
   ```

### Troubleshooting

#### Common Issues
1. **Audio Sync Issues**
   - Check device sample rates
   - Verify buffer sizes
   - Monitor system load
   - Review timestamp alignment

2. **Video Quality Issues**
   - Verify FFmpeg settings
   - Check system resources
   - Monitor encoding performance
   - Validate resolution settings

#### Debugging Tools
```python
# Debug logging example
def debug_audio_stream(self):
    """
    Monitor audio stream parameters
    """
    print(f"Sample Rate: {self.sample_rate}")
    print(f"Buffer Size: {self.buffer_size}")
    print(f"Format: {self.audio_format}")
    print(f"Latency: {self.get_latency()}ms")
```

## Contributing

### Code Style
- Follow PEP 8 guidelines
- Use type hints
- Document all functions
- Include unit tests

### Pull Request Process
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit pull request

## License

MIT License - see LICENSE file for details

# Audio Implementation Deep Dive
> which took me almost 2 days to sort out

#### Core Technologies

1. **ctypes Integration**
```python
# Windows API structure definitions using ctypes
class WAVEFORMATEX(Structure):
    _fields_ = [
        ('wFormatTag', WORD),
        ('nChannels', WORD),
        ('nSamplesPerSec', DWORD),
        ('nAvgBytesPerSec', DWORD),
        ('nBlockAlign', WORD),
        ('wBitsPerSample', WORD),
        ('cbSize', WORD)
    ]

class WAVEFORMATEXTENSIBLE(Structure):
    _pack_ = 1
    class Samples(Union):
        _fields_ = [
            ('wValidBitsPerSample', WORD),
            ('wSamplesPerBlock', WORD),
            ('wReserved', WORD),
        ]
```
- Used for direct Windows API interaction
- Enables low-level audio device control
- Provides structure definitions for audio formats
- Handles memory management for native calls

2. **PyCaw (Python Core Audio Windows)**
```python
from pycaw.pycaw import AudioUtilities, IAudioClient

# Device enumeration example
devices = AudioUtilities.GetAllDevices()
```
- Provides Python wrapper for Windows Core Audio
- Simplifies audio device enumeration
- Manages audio session control
- Handles volume and muting controls

#### Audio Data Flow

1. **Capture Pipeline**
```
Raw Audio Data (32-bit float)
    ↓
Buffer Collection (10ms chunks)
    ↓
Format Conversion (to 16-bit PCM)
    ↓
Activity Detection
    ↓
WAV File Writing
```

2. **Data Format Details**
```python
# Audio format specifications
AUDIO_FORMATS = {
    'capture': {
        'format': WAVE_FORMAT_IEEE_FLOAT,
        'channels': 2,
        'sample_rate': 44100,
        'bits_per_sample': 32,
        'block_align': 8,  # channels * (bits_per_sample / 8)
        'bytes_per_sec': 352800  # sample_rate * block_align
    },
    'storage': {
        'format': WAVE_FORMAT_PCM,
        'channels': 2,
        'sample_rate': 44100,
        'bits_per_sample': 16,
        'block_align': 4,
        'bytes_per_sec': 176400
    }
}
```

#### WASAPI Implementation Details

1. **Initialization Process**
```python
def initialize_wasapi_client(device):
    # Get mix format
    wave_format_ptr = audio_client.GetMixFormat()
    wave_format = cast(wave_format_ptr, POINTER(WAVEFORMATEX)).contents
    
    # Check for extended format
    if wave_format.wFormatTag == WAVE_FORMAT_EXTENSIBLE:
        wave_format_ext = cast(wave_format_ptr, 
                             POINTER(WAVEFORMATEXTENSIBLE)).contents
        is_float = (wave_format_ext.SubFormat == 
                   KSDATAFORMAT_SUBTYPE_IEEE_FLOAT)
    else:
        is_float = (wave_format.wFormatTag == WAVE_FORMAT_IEEE_FLOAT)
```

2. **Buffer Management**
```python
class AudioBuffer:
    def __init__(self, format_info):
        self.frame_size = format_info['channels'] * \
                         (format_info['bits_per_sample'] // 8)
        self.frames_per_buffer = int(format_info['sample_rate'] * 0.01)  # 10ms
        self.buffer_size = self.frame_size * self.frames_per_buffer
        
    def process_buffer(self, buffer_data):
        if format_info['is_float']:
            # Convert from float32 to int16
            float_data = np.frombuffer(buffer_data, dtype=np.float32)
            return (float_data * 32767).astype(np.int16)
        return np.frombuffer(buffer_data, dtype=np.int16)
```

3. **Device State Management**
```python
class DeviceState:
    def __init__(self):
        self.active = False
        self.last_active_time = 0
        self.buffer_stats = {
            'total_frames': 0,
            'empty_packets': 0,
            'underruns': 0
        }
    
    def update_activity(self, buffer_data):
        if np.max(np.abs(buffer_data)) > ACTIVITY_THRESHOLD:
            self.active = True
            self.last_active_time = time.time()
```

#### Audio Processing Pipeline

1. **Sample Rate Conversion**
```python
def convert_sample_rate(data, src_rate, dst_rate):
    """
    Converts audio data between sample rates using linear interpolation
    """
    if src_rate == dst_rate:
        return data
    
    duration = len(data) / src_rate
    output_size = int(duration * dst_rate)
    time_old = np.linspace(0, duration, len(data))
    time_new = np.linspace(0, duration, output_size)
    
    return np.interp(time_new, time_old, data)
```

2. **Format Conversion Details**
```python
def convert_audio_format(data, src_format, dst_format):
    """
    Handles conversion between different audio formats
    """
    if src_format['is_float']:
        # Float32 to Int16
        float_data = np.frombuffer(data, dtype=np.float32)
        return (float_data * 32767).astype(np.int16)
    elif dst_format['is_float']:
        # Int16 to Float32
        int_data = np.frombuffer(data, dtype=np.int16)
        return (int_data / 32767).astype(np.float32)
    return data
```

3. **Buffer Underrun Handling**
```python
def handle_buffer_underrun(self, elapsed_time):
    """
    Generates silence frames for buffer underruns
    """
    frames_needed = int(elapsed_time * self.sample_rate)
    silence_data = np.zeros(frames_needed * self.channels, 
                           dtype=np.int16)
    return silence_data.tobytes()
```

#### Performance Optimizations

1. **Memory Management**
```python
class AudioBufferPool:
    """
    Implements buffer pooling to reduce memory allocation overhead
    """
    def __init__(self, buffer_size, pool_size=10):
        self.pool = [bytearray(buffer_size) for _ in range(pool_size)]
        self.available = self.pool.copy()
        
    def get_buffer(self):
        if not self.available:
            # Create new buffer if pool is empty
            return bytearray(self.pool[0].size)
        return self.available.pop()
```

2. **Thread Synchronization**
```python
class ThreadSafeBuffer:
    """
    Thread-safe buffer implementation for audio data
    """
    def __init__(self, max_size):
        self.buffer = collections.deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.not_empty = threading.Condition(self.lock)
        
    def put(self, data):
        with self.lock:
            self.buffer.append(data)
            self.not_empty.notify()
```

### Core Audio Features and Technical Highlights

1. **Device Enumeration and Hot-plug**
```python
def get_available_devices():
    """
    Dynamically discovers and monitors audio devices:
    - System default device tracking
    - HDMI audio detection
    - Device state monitoring
    - Hot-plug event handling
    """
```
- Real-time device state monitoring
- Automatic default device detection
- HDMI audio endpoint identification
- Device removal/addition handling

2. **WASAPI Loopback Capture**
```python
def initialize_loopback_capture():
    """
    System audio capture implementation:
    - Exclusive mode support
    - Direct hardware access
    - Low-latency streaming
    - Format negotiation
    """
```
- Zero-copy buffer management
- Direct memory access
- Hardware timestamp synchronization
- Format negotiation with audio driver

3. **Multi-track Audio Recording**
```python
def record_multiple_devices():
    """
    Simultaneous multi-device recording:
    - Independent device streams
    - Synchronized timestamps
    - Separate file handling
    - Resource management
    """
```
- Thread-per-device management
- Inter-stream synchronization
- Unified timestamp reference
- Resource sharing optimization

4. **Silent Frame Management**
```python
def handle_silence():
    """
    Intelligent silence handling:
    - Activity detection
    - Frame interpolation
    - Buffer continuity
    - Timestamp maintenance
    """
```
- Adaptive threshold detection
- Intelligent frame insertion
- Timestamp continuity preservation
- Buffer underrun prevention

5. **HDMI Audio Processing**
```python
def handle_hdmi_audio():
    """
    HDMI-specific audio handling:
    - Format detection
    - Channel mapping
    - Device switching
    - Error recovery
    """
```
- Dynamic format adaptation
- Multi-channel support
- Device state recovery
- Format conversion handling

6. **Format Conversion Pipeline**
```python
def format_conversion():
    """
    Audio format conversion chain:
    - Sample rate conversion
    - Bit depth adaptation
    - Channel mapping
    - Format transformation
    """
```
- Real-time sample rate conversion
- Float32 to Int16 conversion
- Channel count adaptation
- Format header management

7. **Buffer Management System**
```python
def manage_buffers():
    """
    Advanced buffer management:
    - Pool allocation
    - Memory optimization
    - Thread safety
    - Overflow protection
    """
```
- Zero-copy optimization
- Memory pool management
- Thread-safe operations
- Overflow/underflow protection

8. **Multi-track Synchronization**
```python
def sync_audio_tracks():
    """
    Audio track synchronization:
    - Timestamp alignment
    - Drift compensation
    - Gap detection
    - Frame alignment
    """
```
- Sample-accurate alignment
- Drift detection and correction
- Gap filling strategies
- Frame boundary alignment

9. **Error Recovery System**
```python
def handle_errors():
    """
    Comprehensive error handling:
    - Device disconnection
    - Format changes
    - Buffer errors
    - Stream recovery
    """
```
- Automatic stream recovery
- Format change handling
- Buffer error correction
- Device reconnection logic

10. **Performance Optimization**
```python
def optimize_performance():
    """
    Performance enhancement features:
    - Thread prioritization
    - Memory management
    - CPU utilization
    - Latency optimization
    """
```
- Thread priority management
- Memory allocation optimization
- CPU load balancing
- Latency minimization

11. **Device State Management**
```python
def manage_device_state():
    """
    Device state tracking and control:
    - State transitions
    - Event handling
    - Error recovery
    - Resource cleanup
    """
```
- State machine implementation
- Event-driven architecture
- Resource lifecycle management
- Clean shutdown handling

12. **Audio Quality Control**
```python
def control_quality():
    """
    Audio quality management:
    - Signal monitoring
    - Quality metrics
    - Format validation
    - Artifact prevention
    """
```
- Signal quality monitoring
- Format validation
- Artifact detection
- Quality metrics tracking

### Technical Highlights

1. **Zero-Copy Buffer Management**
- Direct memory access for audio data
- Minimal memory allocation
- Efficient data transfer
- Reduced CPU overhead

2. **Adaptive Format Handling**
- Dynamic format negotiation
- Automatic conversion
- Quality preservation
- Performance optimization

3. **Robust Error Recovery**
- Automatic stream restoration
- Seamless device switching
- Data continuity preservation
- Error isolation

4. **High Performance Architecture**
- Multi-threaded design
- Resource pooling
- Optimized memory usage
- Minimal latency
