# 新建文件 audio_recorder.py，用于封装音频录制功能
import comtypes
import ctypes
import threading
import wave
import time
import numpy as np
from datetime import datetime
from comtypes import CLSCTX_ALL, CoCreateInstance, GUID, COMMETHOD, HRESULT, IUnknown
from ctypes import POINTER, byref, sizeof, c_float, c_ulong, cast, c_uint
from ctypes.wintypes import (DWORD, LPCWSTR, LPWSTR, WORD, UINT, INT, BOOL,
                            BYTE, VARIANT_BOOL, HANDLE, LPVOID)
from ctypes import c_uint32 as UINT32
from ctypes import c_uint64 as UINT64
from pycaw.pycaw import AudioUtilities, IAudioClient

# 定义常量
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
REFERENCE_TIME = ctypes.c_longlong

# 定义音频格式 GUID
KSDATAFORMAT_SUBTYPE_IEEE_FLOAT = GUID('{00000003-0000-0010-8000-00aa00389b71}')
KSDATAFORMAT_SUBTYPE_PCM = GUID('{00000001-0000-0010-8000-00aa00389b71}')

# 定义 GUID
CLSID_MMDeviceEnumerator = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
IID_IMMDeviceEnumerator = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
IID_IAudioCaptureClient = GUID('{C8ADBD64-E71E-48A0-A4DE-185C395CD317}')

# 定义结构体
class PROPERTYKEY(ctypes.Structure):
    _fields_ = [
        ('fmtid', GUID),
        ('pid', DWORD),
    ]

class PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ('vt', WORD),
        ('wReserved1', WORD),
        ('wReserved2', WORD),
        ('wReserved3', WORD),
        ('data', DWORD * 4),
    ]

class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('wFormatTag', ctypes.c_ushort),
        ('nChannels', ctypes.c_ushort),
        ('nSamplesPerSec', ctypes.c_uint),
        ('nAvgBytesPerSec', ctypes.c_uint),
        ('nBlockAlign', ctypes.c_ushort),
        ('wBitsPerSample', ctypes.c_ushort),
        ('cbSize', ctypes.c_ushort),
    ]

class WAVEFORMATEXTENSIBLE(ctypes.Structure):
    _pack_ = 1
    class SamplesUnion(ctypes.Union):
        _fields_ = [
            ('wValidBitsPerSample', ctypes.c_ushort),
            ('wSamplesPerBlock', ctypes.c_ushort),
            ('wReserved', ctypes.c_ushort),
        ]
    _fields_ = [
        ('Format', WAVEFORMATEX),
        ('Samples', SamplesUnion),
        ('dwChannelMask', ctypes.c_uint),
        ('SubFormat', comtypes.GUID),
    ]

# 定义接口
class IAudioCaptureClient(IUnknown):
    _iid_ = IID_IAudioCaptureClient
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetBuffer',
                  (['out'], POINTER(LPVOID), 'ppData'),
                  (['out'], POINTER(UINT32), 'pNumFramesToRead'),
                  (['out'], POINTER(DWORD), 'pdwFlags'),
                  (['out'], POINTER(UINT64), 'pu64DevicePosition'),
                  (['out'], POINTER(UINT64), 'pu64QPCPosition')),
        COMMETHOD([], HRESULT, 'ReleaseBuffer',
                  (['in'], UINT32, 'NumFramesRead')),
        COMMETHOD([], HRESULT, 'GetNextPacketSize',
                  (['out'], POINTER(UINT32), 'pNumFramesInNextPacket')),
    ]

class IPropertyStore(IUnknown):
    _iid_ = GUID('{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetCount',
                  (['out'], POINTER(DWORD), 'cProps')),
        COMMETHOD([], HRESULT, 'GetAt',
                  (['in'], DWORD, 'iProp'),
                  (['out'], POINTER(PROPERTYKEY), 'pkey')),
        COMMETHOD([], HRESULT, 'GetValue',
                  (['in'], POINTER(PROPERTYKEY), 'key'),
                  (['out'], POINTER(PROPVARIANT), 'pv')),
        COMMETHOD([], HRESULT, 'SetValue',
                  (['in'], POINTER(PROPERTYKEY), 'key'),
                  (['in'], POINTER(PROPVARIANT), 'propvar')),
        COMMETHOD([], HRESULT, 'Commit')
    ]

class IMMDevice(IUnknown):
    _iid_ = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'Activate',
                  (['in'], POINTER(comtypes.GUID), 'iid'),
                  (['in'], DWORD, 'dwClsCtx'),
                  (['in'], POINTER(DWORD), 'pActivationParams'),
                  (['out','retval'], POINTER(POINTER(IUnknown)), 'ppInterface')),
        COMMETHOD([], HRESULT, 'OpenPropertyStore',
                  (['in'], DWORD, 'stgmAccess'),
                  (['out','retval'], POINTER(POINTER(IPropertyStore)), 'ppProperties')),
        COMMETHOD([], HRESULT, 'GetId',
                  (['out','retval'], POINTER(LPCWSTR), 'ppstrId')),
        COMMETHOD([], HRESULT, 'GetState',
                  (['out','retval'], POINTER(DWORD), 'pdwState')),
    ]

class IMMDeviceCollection(IUnknown):
    _iid_ = GUID('{0BD7A1BE-7A1A-44DB-8397-CC5392387B5E}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetCount',
                  (['out', 'retval'], POINTER(c_uint), 'pcDevices')),
        COMMETHOD([], HRESULT, 'Item',
                  (['in'], c_uint, 'nDevice'),
                  (['out', 'retval'], POINTER(POINTER(IMMDevice)), 'ppDevice')),
    ]

class IMMNotificationClient(IUnknown):
    _iid_ = GUID('{7991EEC9-7E89-4D85-8390-6C703CEC60C0}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'OnDeviceStateChanged',
                  (['in'], LPCWSTR, 'pwstrDeviceId'),
                  (['in'], DWORD, 'dwNewState')),
        COMMETHOD([], HRESULT, 'OnDeviceAdded',
                  (['in'], LPCWSTR, 'pwstrDeviceId')),
        COMMETHOD([], HRESULT, 'OnDeviceRemoved',
                  (['in'], LPCWSTR, 'pwstrDeviceId')),
        COMMETHOD([], HRESULT, 'OnDefaultDeviceChanged',
                  (['in'], DWORD, 'flow'),
                  (['in'], DWORD, 'role'),
                  (['in'], LPCWSTR, 'pwstrDefaultDeviceId')),
        COMMETHOD([], HRESULT, 'OnPropertyValueChanged',
                  (['in'], LPCWSTR, 'pwstrDeviceId'),
                  (['in'], PROPERTYKEY, 'key'))
    ]

class IMMDeviceEnumerator(IUnknown):
    _iid_ = IID_IMMDeviceEnumerator
    _methods_ = [
        COMMETHOD([], HRESULT, 'EnumAudioEndpoints',
                  (['in'], DWORD, 'dataFlow'),
                  (['in'], DWORD, 'dwStateMask'),
                  (['out','retval'], POINTER(POINTER(IMMDeviceCollection)), 'ppDevices')),
        COMMETHOD([], HRESULT, 'GetDefaultAudioEndpoint',
                  (['in'], DWORD, 'dataFlow'),
                  (['in'], DWORD, 'role'),
                  (['out','retval'], POINTER(POINTER(IMMDevice)), 'ppEndpoint')),
        COMMETHOD([], HRESULT, 'GetDevice',
                  (['in'], LPCWSTR, 'pwstrId'),
                  (['out','retval'], POINTER(POINTER(IMMDevice)), 'ppDevice')),
        COMMETHOD([], HRESULT, 'RegisterEndpointNotificationCallback',
                  (['in'], POINTER(IMMNotificationClient))),
        COMMETHOD([], HRESULT, 'UnregisterEndpointNotificationCallback',
                  (['in'], POINTER(IMMNotificationClient))),
    ]

class AudioRecorderManager:
    """音频录制管理器，负责管理多个设备的录制"""
    def __init__(self):
        self.is_recording = False
        self.audio_clients = []
        self.recording_threads = []
        self.start_time = None
        
        # 初始化 COM
        comtypes.CoInitialize()

    def get_available_devices(self):
        """获取所有可用的音频设备"""
        output_devices = []
        input_devices = []
        
        try:
            # 创建设备枚举器
            enumerator = CoCreateInstance(
                CLSID_MMDeviceEnumerator,
                IMMDeviceEnumerator,
                CLSCTX_ALL
            )
            
            # 获取默认输出设备
            try:
                default_output = enumerator.GetDefaultAudioEndpoint(0, 1)  # eRender = 0, eConsole = 1
                default_output_id = ctypes.wstring_at(default_output.GetId())
                print(f"[Audio] Default output device ID: {default_output_id}")
            except Exception as e:
                print(f"[Audio] Error getting default output device: {e}")
                default_output_id = None
            
            # 获取输出设备
            collection = enumerator.EnumAudioEndpoints(0, 1)  # eRender = 0
            count = collection.GetCount()
            
            audio_devices = AudioUtilities.GetAllDevices()
            device_names = {dev.id: dev.FriendlyName for dev in audio_devices}
            
            for i in range(count):
                try:
                    device = collection.Item(i)
                    device_id_ptr = device.GetId()
                    if device_id_ptr:
                        device_id = ctypes.wstring_at(device_id_ptr)
                        friendly_name = device_names.get(device_id, f"输出设备 {i}")
                        output_devices.append({
                            'name': friendly_name,
                            'device': device,
                            'id': device_id,
                            'is_default': device_id == default_output_id
                        })
                except Exception as e:
                    print(f"处理输出设备 {i} 时出错: {str(e)}")
            
            # 获取输入设备
            collection = enumerator.EnumAudioEndpoints(1, 1)  # eCapture = 1
            count = collection.GetCount()
            
            for i in range(count):
                try:
                    device = collection.Item(i)
                    device_id_ptr = device.GetId()
                    if device_id_ptr:
                        device_id = ctypes.wstring_at(device_id_ptr)
                        friendly_name = device_names.get(device_id, f"输入设备 {i}")
                        input_devices.append({
                            'name': friendly_name,
                            'device': device,
                            'id': device_id
                        })
                except Exception as e:
                    print(f"处理输入设备 {i} 时出错: {str(e)}")
                    
        except Exception as e:
            print(f"获取设备列表时出错: {str(e)}")
            
        return output_devices, input_devices

    def _initialize_audio_client(self, device, is_input=False):
        """初始化音频客户端"""
        # 激活设备的 IAudioClient 接口
        audio_interface = device.Activate(
            IAudioClient._iid_, CLSCTX_ALL, None)
        audio_client = audio_interface.QueryInterface(IAudioClient)
        
        # 获取设备的原生格式
        wave_format_ptr = audio_client.GetMixFormat()
        wave_format = ctypes.cast(wave_format_ptr, POINTER(WAVEFORMATEX)).contents
        
        # 检查是否为扩展格式
        if wave_format.wFormatTag == 0xFFFE:  # WAVE_FORMAT_EXTENSIBLE
            wave_format_ext = ctypes.cast(wave_format_ptr, POINTER(WAVEFORMATEXTENSIBLE)).contents
            sub_format = wave_format_ext.SubFormat
            is_float = (sub_format == KSDATAFORMAT_SUBTYPE_IEEE_FLOAT)
        else:
            is_float = (wave_format.wFormatTag == 3)  # WAVE_FORMAT_IEEE_FLOAT
        
        # 初始化音频客户端
        buffer_duration = REFERENCE_TIME(int(10000000))  # 1秒
        flags = 0 if is_input else AUDCLNT_STREAMFLAGS_LOOPBACK
        hr = audio_client.Initialize(
            AUDCLNT_SHAREMODE_SHARED,
            flags,
            buffer_duration,
            0,
            wave_format_ptr,
            None
        )
        
        if hr != 0:
            raise Exception(f"初始化音频客户端失败，错误代码：{hr}")
        
        # 获取捕获客户端
        capture_client = audio_client.GetService(IID_IAudioCaptureClient)
        capture_client = capture_client.QueryInterface(IAudioCaptureClient)
        
        return {
            'client': audio_client,
            'capture': capture_client,
            'format': {
                'channels': wave_format.nChannels,
                'sample_rate': wave_format.nSamplesPerSec,
                'bits_per_sample': wave_format.wBitsPerSample,
                'is_float': is_float
            }
        }

    def _record_device_audio(self, client_info, start_time):
        """录制单个设备的音频"""
        try:
            audio_client = client_info['client']
            capture_client = client_info['capture']
            format_info = client_info['format']
            filename = client_info['filename']
            
            print(f"\n[Audio] Device recording start - {filename}")
            print(f"[Audio] Format: {format_info}")
            print(f"[Audio] Start timestamp: {time.time()}")
            
            # 开始录制
            audio_client.Start()
            
            buffer_stats = {
                'total_frames': 0,
                'total_packets': 0,
                'empty_packets': 0,
                'last_packet_time': time.time()
            }
            
            with wave.open(filename, 'wb') as wave_file:
                wave_file.setnchannels(format_info['channels'])
                wave_file.setsampwidth(2 if format_info['is_float'] else format_info['bits_per_sample'] // 8)
                wave_file.setframerate(format_info['sample_rate'])
                
                # 计算每10ms的帧数
                frames_per_10ms = int(format_info['sample_rate'] * 0.01)
                
                # 准备空白帧（10ms的数据）
                silence_data = np.zeros(frames_per_10ms * format_info['channels'], 
                                      dtype=np.int16).tobytes()
                
                # 跟踪设备活动状态
                last_write_time = time.time()
                device_active = False
                active_duration = 0
                last_active_check = time.time()
                
                while self.is_recording:
                    current_time = time.time()
                    packet_length = capture_client.GetNextPacketSize()
                    buffer_stats['total_packets'] += 1
                    
                    if packet_length > 0:
                        buffer, num_frames, flags, _, _ = capture_client.GetBuffer()
                        buffer_stats['total_frames'] += num_frames
                        
                        if buffer:
                            if buffer_stats['total_packets'] % 100 == 0:  # 每100个包打印一次统计
                                # print(f"[Audio] Buffer stats: {buffer_stats}")
                                # print(f"[Audio] Current delay: {current_time - buffer_stats['last_packet_time']:.3f}s")
                                buffer_stats['last_packet_time'] = current_time
                        else:
                            buffer_stats['empty_packets'] += 1
                        
                        if buffer_stats['total_packets'] % 100 == 0:  # 每100个包打印一次统计
                            # print(f"[Audio] Buffer stats: {buffer_stats}")
                            # print(f"[Audio] Current delay: {current_time - buffer_stats['last_packet_time']:.3f}s")
                            buffer_stats['last_packet_time'] = current_time
                        
                        buffer_size = num_frames * format_info['channels'] * (format_info['bits_per_sample'] // 8)
                        audio_data = ctypes.string_at(buffer, buffer_size)
                        
                        if format_info['is_float']:
                            float_data = np.frombuffer(audio_data, dtype=np.float32)
                            if np.max(np.abs(float_data)) > 0.0001:
                                device_active = True
                                active_duration += current_time - last_active_check
                            audio_data = (float_data * 32767).astype(np.int16).tobytes()
                        else:
                            int_data = np.frombuffer(audio_data, dtype=np.int16)
                            if np.max(np.abs(int_data)) > 10:
                                device_active = True
                                active_duration += current_time - last_active_check
                            
                        wave_file.writeframes(audio_data)
                        last_write_time = current_time
                        
                        capture_client.ReleaseBuffer(num_frames)
                    else:
                        # 只在设备未激活或激活时间不足100ms时插入空白帧
                        if not device_active or active_duration < 0.1:
                            elapsed = current_time - last_write_time
                            if elapsed >= 0.01:
                                frames_needed = int(elapsed * format_info['sample_rate'])
                                if frames_needed > 0:
                                    silence = np.zeros(frames_needed * format_info['channels'], 
                                                     dtype=np.int16).tobytes()
                                    wave_file.writeframes(silence)
                                    last_write_time = current_time
                        
                        time.sleep(0.001)
                    
                    last_active_check = current_time
                
            print(f"\n[Audio] Final buffer stats for {filename}:")
            print(f"Total frames: {buffer_stats['total_frames']}")
            print(f"Total packets: {buffer_stats['total_packets']}")
            print(f"Empty packets: {buffer_stats['empty_packets']}")
            
        except Exception as e:
            print(f"[Audio] Recording error: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            audio_client.Stop()
            print(f"停止录制设备: {filename}")

    def start_recording(self, selected_outputs=None, selected_input=None, base_filename=None):
        """开始录制指定的设备"""
        try:
            print(f"\n[Audio] Manager start_recording called at: {time.time()}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = base_filename or f"recording_{timestamp}"
            
            self.audio_clients = []
            
            if selected_outputs:
                for device in selected_outputs:
                    try:
                        client_info = self._initialize_audio_client(device['device'], is_input=False)
                        if client_info:
                            self.audio_clients.append({
                                'device': device['device'],
                                'client': client_info['client'],
                                'capture': client_info['capture'],
                                'format': client_info['format'],
                                'filename': f"{base_filename}_output_{device['name']}.wav",
                                'is_input': False
                            })
                    except Exception as e:
                        print(f"初始化输出设备失败: {str(e)}")
            
            if selected_input:
                try:
                    client_info = self._initialize_audio_client(selected_input['device'], is_input=True)
                    if client_info:
                        self.audio_clients.append({
                            'device': selected_input['device'],
                            'client': client_info['client'],
                            'capture': client_info['capture'],
                            'format': client_info['format'],
                            'filename': f"{base_filename}_input.wav",
                            'is_input': True
                        })
                except Exception as e:
                    print(f"初始化输入设备失败: {str(e)}")
            
            if not self.audio_clients:
                raise Exception("没有可用的录制设备")
            
            self.is_recording = True
            self.start_time = time.time()
            print(f"[Audio] All devices initialized, starting threads at: {self.start_time}")
            
            for client_info in self.audio_clients:
                thread = threading.Thread(
                    target=self._record_device_audio,
                    args=(client_info, self.start_time)
                )
                self.recording_threads.append(thread)
                thread.start()
            
            return [client['filename'] for client in self.audio_clients]
            
        except Exception as e:
            print(f"开始录制失败: {str(e)}")
            self.stop_recording()
            raise

    def stop_recording(self):
        """止所有设备的录制"""
        if self.is_recording:
            self.is_recording = False
            
            for thread in self.recording_threads:
                thread.join(timeout=5)
            
            self.recording_threads = []
            self.audio_clients = []

    def __del__(self):
        """清理资源"""
        self.stop_recording()
        comtypes.CoUninitialize() 