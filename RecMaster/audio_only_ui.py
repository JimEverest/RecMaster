import comtypes
import ctypes
import threading
import wave
import sys
import time
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QComboBox, QPushButton, QLabel, QMessageBox, QGroupBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, QTimer, QEvent
from comtypes import CLSCTX_ALL, CoCreateInstance, GUID, COMMETHOD, HRESULT, IUnknown
from ctypes import POINTER, byref, sizeof, c_float, c_ulong, cast, c_uint
from ctypes.wintypes import (DWORD, LPCWSTR, LPWSTR, WORD, UINT, INT, BOOL,
                            BYTE, VARIANT_BOOL, HANDLE, LPVOID)
from ctypes import c_uint32 as UINT32
from ctypes import c_uint64 as UINT64
from pycaw.pycaw import AudioUtilities, IAudioClient
from datetime import datetime

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

# 定义 WAVEFORMATEX 结构
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

# 定义 WAVEFORMATEXTENSIBLE 结构
class WAVEFORMATEXTENSIBLE(ctypes.Structure):
    _pack_ = 1  # 设置字节对齐
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

# 定义 IAudioCaptureClient 接口
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

# 然后定义接口类
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

# 然后定义 IMMDeviceEnumerator
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

class AudioRecorderUI(QMainWindow):
    def __init__(self):
        try:
            print("初始化 AudioRecorderUI...")
            super().__init__()
            self.setWindowTitle("系统声音录制器")
            self.setGeometry(100, 100, 400, 300)
            
            print("初始化录制状态...")
            # 初始化录制状态
            self.is_recording = False
            self.current_device = None
            
            print("创建主界面...")
            # 创建主界面
            self.init_ui()
            
            print("获取可用设备列表...")
            # 获取可用设备列
            self.update_device_list()
            print("AudioRecorderUI 初始化完成")
            
        except Exception as e:
            print(f"AudioRecorderUI 初始化失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # === 输出设备选择部分 ===
        output_group = QGroupBox("输出设备")
        output_layout = QVBoxLayout(output_group)
        
        # 输出设备列表
        self.output_list = QListWidget()
        self.output_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        output_layout.addWidget(self.output_list)
        
        # 刷新设备按钮
        self.refresh_button = QPushButton("刷新设备列表")
        self.refresh_button.clicked.connect(self.update_device_list)
        output_layout.addWidget(self.refresh_button)
        
        layout.addWidget(output_group)
        
        # === 输入设备选择部分 ===
        input_group = QGroupBox("输入设备")
        input_layout = QVBoxLayout(input_group)
        
        # 输入设备下拉框
        self.input_combo = QComboBox()
        input_layout.addWidget(self.input_combo)
        
        layout.addWidget(input_group)
        
        # === 录制控制部分 ===
        control_group = QGroupBox("录制控制")
        control_layout = QVBoxLayout(control_group)
        
        # 录制按钮
        self.record_button = QPushButton("开始录制")
        self.record_button.clicked.connect(self.toggle_recording)
        control_layout.addWidget(self.record_button)
        
        # 状态显示
        self.status_label = QLabel("就绪")
        control_layout.addWidget(self.status_label)
        
        # 计时器显示
        self.timer_label = QLabel("00:00:00")
        control_layout.addWidget(self.timer_label)
        
        layout.addWidget(control_group)
        
        # 初始化计时器
        self.record_timer = QTimer()
        self.record_timer.timeout.connect(self.update_timer)
        self.record_time = 0

    def update_device_list(self):
        """更新可用音频设备列表"""
        print("开始更新设备列表...")
        self.output_list.clear()
        self.input_combo.clear()
        
        try:
            # 添加"关闭"选项到输入设备列表
            self.input_combo.addItem("关闭", None)
            
            # 添加"关闭"选项到输出设备列表
            self.output_list.addItem("关闭")
            
            # 创建设备枚举器
            print("正在创建设备枚举器...")
            enumerator = CoCreateInstance(
                CLSID_MMDeviceEnumerator,
                IMMDeviceEnumerator,
                CLSCTX_ALL
            )
            print("设备枚举器创建成功")
            
            # 获取所有音频输出端点设备
            print("正在枚举音频端点...")
            
            # 枚举输出设备
            collection = enumerator.EnumAudioEndpoints(0, 1)  # eRender = 0
            count = collection.GetCount()
            print(f"找到 {count} 个输出设备")
            
            # 使用 AudioUtilities 获取设备列表作为备用信息源
            audio_devices = AudioUtilities.GetAllDevices()
            device_names = {dev.id: dev.FriendlyName for dev in audio_devices}
            
            for i in range(count):
                try:
                    device = collection.Item(i)
                    device_id_ptr = device.GetId()
                    if device_id_ptr:
                        device_id = ctypes.wstring_at(device_id_ptr)
                        friendly_name = device_names.get(device_id, f"输出设备 {i}")
                        item = QListWidgetItem(friendly_name)
                        item.setData(Qt.ItemDataRole.UserRole, device)
                        self.output_list.addItem(item)
                except Exception as e:
                    print(f"处理输出设备 {i} 时出错: {str(e)}")
            
            # 枚举输入设备
            collection = enumerator.EnumAudioEndpoints(1, 1)  # eCapture = 1
            count = collection.GetCount()
            print(f"找到 {count} 个输入设备")
            
            for i in range(count):
                try:
                    device = collection.Item(i)
                    device_id_ptr = device.GetId()
                    if device_id_ptr:
                        device_id = ctypes.wstring_at(device_id_ptr)
                        friendly_name = device_names.get(device_id, f"输入设备 {i}")
                        self.input_combo.addItem(friendly_name, device)
                except Exception as e:
                    print(f"处理输入设备 {i} 时出错: {str(e)}")
            
            print("设备列表更新完成")
            
        except Exception as e:
            print(f"获取设备列表时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"获取设备列表失败: {str(e)}")

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
            
    def start_recording(self):
        try:
            # 获取选中的输出设备
            selected_items = self.output_list.selectedItems()
            
            # 获取选中的输入设备
            input_device = self.input_combo.currentData()
            
            # 创建录制线程列表
            self.recording_threads = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 初始化所有设备的音频客户端
            self.audio_clients = []
            
            # 处理输出设备
            for item in selected_items:
                device = item.data(Qt.ItemDataRole.UserRole)
                if device:
                    try:
                        client_info = self.initialize_audio_client(device, is_input=False)
                        if client_info:
                            self.audio_clients.append({
                                'device': device,
                                'client': client_info['client'],
                                'capture': client_info['capture'],
                                'format': client_info['format'],
                                'filename': f"output_{timestamp}_{item.text()}.wav",
                                'is_input': False
                            })
                    except Exception as e:
                        print(f"初始化输出设备失败: {str(e)}")
            
            # 处理输入设备
            if input_device:
                try:
                    client_info = self.initialize_audio_client(input_device, is_input=True)
                    if client_info:
                        self.audio_clients.append({
                            'device': input_device,
                            'client': client_info['client'],
                            'capture': client_info['capture'],
                            'format': client_info['format'],
                            'filename': f"input_{timestamp}_microphone.wav",
                            'is_input': True
                        })
                except Exception as e:
                    print(f"初始化输入设备失败: {str(e)}")
            
            if not self.audio_clients:
                QMessageBox.warning(self, "错误", "没有可用的录制设备")
                return
            
            # 启动所有设备的录制
            self.is_recording = True
            start_time = time.time()
            
            for client_info in self.audio_clients:
                thread = threading.Thread(
                    target=self.record_device_audio,
                    args=(client_info, start_time)
                )
                self.recording_threads.append(thread)
                thread.start()
            
            # 更新UI
            self.record_button.setText("停止录制")
            self.status_label.setText("正在录制...")
            self.record_time = 0
            self.record_timer.start(1000)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"开始录制失败: {str(e)}")

    def initialize_audio_client(self, device, is_input=False):
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

    def record_device_audio(self, client_info, start_time):
        """为单个设备录制音频"""
        try:
            audio_client = client_info['client']
            capture_client = client_info['capture']
            format_info = client_info['format']
            filename = client_info['filename']
            
            # 开始录制
            audio_client.Start()
            print(f"开始录制设备: {filename}")
            
            # 创建WAV文件
            with wave.open(filename, 'wb') as wave_file:
                wave_file.setnchannels(format_info['channels'])
                wave_file.setsampwidth(2 if format_info['is_float'] else format_info['bits_per_sample'] // 8)
                wave_file.setframerate(format_info['sample_rate'])
                
                # 计算每10ms的帧数（根据设备采样率）
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
                    
                    if packet_length > 0:
                        # 有实际数据时的处理
                        buffer, num_frames, flags, _, _ = capture_client.GetBuffer()
                        
                        if buffer:
                            buffer_size = num_frames * format_info['channels'] * (format_info['bits_per_sample'] // 8)
                            audio_data = ctypes.string_at(buffer, buffer_size)
                            
                            if format_info['is_float']:
                                float_data = np.frombuffer(audio_data, dtype=np.float32)
                                # 检查是否有实际声音（避免静音数据）
                                if np.max(np.abs(float_data)) > 0.0001:  # 声音阈值
                                    device_active = True
                                    active_duration += current_time - last_active_check
                                audio_data = (float_data * 32767).astype(np.int16).tobytes()
                            else:
                                int_data = np.frombuffer(audio_data, dtype=np.int16)
                                if np.max(np.abs(int_data)) > 10:  # 声音阈值
                                    device_active = True
                                    active_duration += current_time - last_active_check
                            
                            wave_file.writeframes(audio_data)
                            last_write_time = current_time
                        
                        capture_client.ReleaseBuffer(num_frames)
                    else:
                        # 只在设备未激活或激活时间不足100ms时插入空白帧
                        if not device_active or active_duration < 0.1:
                            elapsed = current_time - last_write_time
                            if elapsed >= 0.01:  # 每10ms检查一次
                                # 计算需要插入的空白帧数量
                                frames_needed = int(elapsed * format_info['sample_rate'])
                                if frames_needed > 0:
                                    # 创建对应时长的空白数据
                                    silence = np.zeros(frames_needed * format_info['channels'], 
                                                     dtype=np.int16).tobytes()
                                    wave_file.writeframes(silence)
                                    last_write_time = current_time
                        
                        time.sleep(0.001)  # 短暂休眠
                    
                    last_active_check = current_time
                
        except Exception as e:
            print(f"录制设备时出错: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            audio_client.Stop()
            print(f"停止录制设备: {filename}")

    def stop_recording(self):
        if self.is_recording:
            print("正在停止所有录制...")
            self.is_recording = False
            self.record_button.setEnabled(False)
            self.status_label.setText("正在停止录制...")
            
            # 等待所有录制线程结束
            if hasattr(self, 'recording_threads'):
                for thread in self.recording_threads:
                    thread.join(timeout=5)
            
            self.record_button.setEnabled(True)
            self.record_button.setText("开始录制")
            self.status_label.setText("录制已完成")
            self.record_timer.stop()

    def update_timer(self):
        self.record_time += 1
        hours = self.record_time // 3600
        minutes = (self.record_time % 3600) // 60
        seconds = self.record_time % 60
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
    def closeEvent(self, event):
        """关闭窗口时停止录制"""
        if self.is_recording:
            self.stop_recording()
        event.accept()

    def update_ui_after_recording(self):
        """在主线程中更新 UI"""
        if QApplication.instance():
            QApplication.instance().postEvent(self, RecordingFinishedEvent())

# 添加自定义事件类
class RecordingFinishedEvent(QEvent):
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())
    
    def __init__(self):
        super().__init__(self.EVENT_TYPE)

def event(self, event):
    """处理自定义事件"""
    if event.type() == RecordingFinishedEvent.EVENT_TYPE:
        self.record_button.setEnabled(True)
        self.record_button.setText("开始录制")
        self.status_label.setText("录制已完成")
        self.record_timer.stop()
        return True
    return super().event(event)

def main():
    try:
        print("程序启动...")
        # 初始化 COM
        print("正在初始化 COM...")
        comtypes.CoInitialize()
        print("COM 初始化成功")
        
        print("正在创建应用程序...")
        app = QApplication(sys.argv)
        
        print("正在创建主窗口...")
        window = AudioRecorderUI()
        
        print("显示主窗口...")
        window.show()
        
        print("进入主事件循环...")
        result = app.exec()
        
        print(f"应用程序退出，返回值: {result}")
        return result
        
    except Exception as e:
        print(f"程序出错: {str(e)}")
        import traceback
        traceback.print_exc()
        # 显示错误对话框
        if QApplication.instance():
            QMessageBox.critical(None, "错误", f"程序发生错误:\n{str(e)}")
        return 1
    finally:
        try:
            print("正在清理 COM...")
            comtypes.CoUninitialize()
            print("COM 清理完成")
        except Exception as e:
            print(f"COM 清理出错: {str(e)}")

if __name__ == "__main__":
    try:
        print("=== 系统声音录制器启动 ===")
        sys.exit(main())
    except Exception as e:
        print(f"主程序异常: {str(e)}")
        traceback.print_exc()
        # 确保错误消息被显示
        if QApplication.instance():
            QMessageBox.critical(None, "致命错误", f"程序遇到致命错误:\n{str(e)}")
        sys.exit(1)
