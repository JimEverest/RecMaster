import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime
import subprocess
import os
import humanize
import traceback
import win32gui
import win32api
import win32con
from ctypes import windll, WINFUNCTYPE, POINTER, Structure, c_int, c_void_p, c_bool, byref
from audio_recorder import AudioRecorderManager
import getpass

# 定义必要的结构和类型
class RECT(Structure):
    _fields_ = [
        ('left', c_int),
        ('top', c_int),
        ('right', c_int),
        ('bottom', c_int)
    ]

class ScreenInfo:
    def __init__(self):
        # 设置进程为DPI感知
        try:
            windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            windll.user32.SetProcessDPIAware()

    @staticmethod
    def get_dpi_scaling(monitor):
        """获取显示器的DPI缩放值"""
        try:
            # 获取监视器句柄对应的DC
            monitor_info = win32api.GetMonitorInfo(monitor)
            monitor_handle = win32api.MonitorFromRect(monitor_info['Monitor'])
            
            # 使用 GetDpiForWindow 获取DPI
            hwnd = win32gui.WindowFromPoint((monitor_info['Monitor'][0], monitor_info['Monitor'][1]))
            dpi = windll.user32.GetDpiForWindow(hwnd)
            
            if dpi:
                return dpi / 96.0
                
            # 备用方法：使用DC获取DPI
            dc = win32gui.GetDC(hwnd)
            dpi_x = win32gui.GetDeviceCaps(dc, win32con.LOGPIXELSX)
            win32gui.ReleaseDC(hwnd, dc)
            
            return dpi_x / 96.0
            
        except Exception as e:
            print(f"Error getting DPI scaling: {e}")
            # 最后的备用方法
            try:
                dc = win32gui.GetDC(0)
                dpi = win32gui.GetDeviceCaps(dc, win32con.LOGPIXELSX)
                win32gui.ReleaseDC(0, dc)
                return dpi / 96.0
            except Exception as e2:
                print(f"Error getting DPI scaling (backup method): {e2}")
                return 1.0

    @staticmethod
    def get_real_resolution():
        """获取所有显示器的真实分辨率（考虑缩放）"""
        # 确保DPI感知已设置
        ScreenInfo()
        
        monitors = []
        
        def callback(monitor, dc, rect, data):
            monitor_info = win32api.GetMonitorInfo(monitor)
            scaling = ScreenInfo.get_dpi_scaling(monitor)
            print(f"Debug - Monitor DPI scaling: {scaling}")
            
            # 获取显示器物理位置
            monitor_rect = monitor_info['Monitor']
            x = monitor_rect[0]
            y = monitor_rect[1]
            width = monitor_rect[2] - monitor_rect[0]
            height = monitor_rect[3] - monitor_rect[1]
            
            # 应用DPI缩放
            real_width = int(width)  # 不需要再次缩放，因为已经是DPI感知的
            real_height = int(height)
            
            monitors.append({
                'x': x,
                'y': y,
                'width': real_width,
                'height': real_height,
                'scaling': scaling
            })
            return True

        # 正确定义回调函数类型
        MONITORENUMPROC = WINFUNCTYPE(c_bool, c_void_p, c_void_p, POINTER(RECT), c_void_p)
        callback_function = MONITORENUMPROC(callback)
        
        # 枚举显示器
        windll.user32.EnumDisplayMonitors(None, None, callback_function, 0)
        
        return monitors

class ScreenRecorder:
    def __init__(self, quality=3):
        self.quality = max(1, min(5, quality))
        self._set_quality_params()
        self.recording = False
        self.output_file = None
        self.current_fps = 0
        self.width = 0
        self.height = 0
        self.process = None
        self.monitors = ScreenInfo.get_real_resolution()
        self.border_hwnd = None

    def _set_quality_params(self):
        # 质量参数配置
        quality_params = {
            1: {  # 最低质量
                'fps': 15,
                'crf': 32,
                'preset': 'ultrafast',
                'video_bitrate': '1000k',
            },
            2: {  # 低质量
                'fps': 20,
                'crf': 28,
                'preset': 'veryfast',
                'video_bitrate': '1500k',
            },
            3: {  # 中等质量
                'fps': 24,
                'crf': 23,
                'preset': 'medium',
                'video_bitrate': '2500k',
            },
            4: {  # 高质量
                'fps': 30,
                'crf': 20,
                'preset': 'slow',
                'video_bitrate': '4000k',
            },
            5: {  # 最高质量
                'fps': 60,
                'crf': 18,
                'preset': 'veryslow',
                'video_bitrate': '6000k',
            }
        }
        
        params = quality_params[self.quality]
        self.fps = params['fps']
        self.crf = params['crf']
        self.preset = params['preset']
        self.video_bitrate = params['video_bitrate']

    def show_recording_border(self, x, y, width, height, master_window):
        """显示录制区域的边框"""
        try:
            # 清理旧的边框窗口
            if hasattr(self, 'border_hwnd') and self.border_hwnd:
                win32gui.DestroyWindow(self.border_hwnd)
                self.border_hwnd = None

            # 注册窗口类
            wc = win32gui.WNDCLASS()
            wc.lpszClassName = "RecordingBorder"
            wc.hbrBackground = win32gui.GetStockObject(win32con.NULL_BRUSH)
            wc.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW
            wc.lpfnWndProc = win32gui.DefWindowProc
            wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
            
            try:
                win32gui.RegisterClass(wc)
            except Exception:
                # 类可能已经注册
                pass

            # 创建窗口
            ex_style = (
                win32con.WS_EX_LAYERED |      # 分层窗口
                win32con.WS_EX_TRANSPARENT |  # 点击穿透
                win32con.WS_EX_TOPMOST       # 总在最前
            )
            style = win32con.WS_POPUP | win32con.WS_VISIBLE

            self.border_hwnd = win32gui.CreateWindowEx(
                ex_style,
                wc.lpszClassName,
                "Border",
                style,
                x, y, width, height,
                0, 0, 0, None
            )

            # 设置窗口透明度和颜色
            win32gui.SetLayeredWindowAttributes(
                self.border_hwnd,
                win32api.RGB(0, 0, 0),  # 黑色将被透明
                255,  # 不透明度
                win32con.LWA_COLORKEY
            )

            # 创建设备上下文
            hdc = win32gui.GetDC(self.border_hwnd)
            
            # 创建画笔
            pen = win32gui.CreatePen(win32con.PS_SOLID, 2, win32api.RGB(255, 0, 0))  # 2像素红色边框
            
            # 选择画笔
            old_pen = win32gui.SelectObject(hdc, pen)
            
            # 画矩形
            win32gui.MoveToEx(hdc, 0, 0)
            win32gui.LineTo(hdc, width - 1, 0)
            win32gui.LineTo(hdc, width - 1, height - 1)
            win32gui.LineTo(hdc, 0, height - 1)
            win32gui.LineTo(hdc, 0, 0)
            
            # 清理资源
            win32gui.SelectObject(hdc, old_pen)
            win32gui.DeleteObject(pen)
            win32gui.ReleaseDC(self.border_hwnd, hdc)

            # 显示窗口
            win32gui.ShowWindow(self.border_hwnd, win32con.SW_SHOW)
            win32gui.UpdateWindow(self.border_hwnd)

            # 创建一个线程来保持边框可见
            def keep_border_visible():
                while self.recording:
                    if self.border_hwnd:
                        try:
                            win32gui.SetWindowPos(
                                self.border_hwnd, win32con.HWND_TOPMOST,
                                x, y, width, height,
                                win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                            )
                        except Exception:
                            break
                    time.sleep(0.1)

            border_thread = threading.Thread(target=keep_border_visible)
            border_thread.daemon = True
            border_thread.start()

            print(f"边框窗口已创建: {width}x{height} at ({x}, {y})")

        except Exception as e:
            print(f"Error showing recording border: {e}")
            traceback.print_exc()

    def start_recording(self, start_x, start_y, end_x, end_y):
        try:
            # 在开始录制视频前记录时间戳
            video_start_time = time.time()
            print(f"\n[Video] About to start recording at: {video_start_time}")
            
            print(f"\n[Video] Recording start timestamp: {time.time()}")
            print(f"Debug - Original coordinates: start=({start_x}, {start_y}), end=({end_x}, {end_y})")
            # 找到选择区域所在的显示器和对应的缩放比例
            scaling = 1.0
            monitor_found = None
            for monitor in self.monitors:
                if (monitor['x'] <= start_x <= monitor['x'] + monitor['width'] and
                    monitor['y'] <= start_y <= monitor['y'] + monitor['height']):
                    scaling = monitor['scaling']
                    monitor_found = monitor
                    break
            
            if monitor_found:
                print(f"Debug - Monitor found: x={monitor_found['x']}, y={monitor_found['y']}, scaling={scaling}")
                # 计算录制区域（坐标已经是DPI感知的）
                left = min(start_x, end_x)
                top = min(start_y, end_y)
                self.width = abs(end_x - start_x)
                self.height = abs(end_y - start_y)
            else:
                left = min(start_x, end_x)
                top = min(start_y, end_y)
                self.width = abs(end_x - start_x)
                self.height = abs(end_y - start_y)
            
            # 确保宽度和高度是偶数
            self.width = self.width - (self.width % 2)
            self.height = self.height - (self.height % 2)
            
            print(f"Debug - Recording area: left={left}, top={top}, width={self.width}, height={self.height}, scaling={scaling}")
            
            # Create output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_file = f'screen_recording_{timestamp}.mp4'
            
            cmd = [
                'ffmpeg',
                '-f', 'gdigrab',
                '-framerate', str(self.fps),
                '-offset_x', str(left),
                '-offset_y', str(top),
                '-video_size', f'{self.width}x{self.height}',
                '-draw_mouse', '1',
                '-i', 'desktop',
                '-c:v', 'libx264',
                '-preset', self.preset,
                '-crf', str(self.crf),
                '-b:v', self.video_bitrate,
                '-pix_fmt', 'yuv420p',
                self.output_file
            ]
            
            # 启动 ffmpeg
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.recording = True
            
            # 在启动ffmpeg后立即记录时间戳
            print(f"[Video] FFmpeg process started at: {time.time()}")
            
            # 返回录制区域的信息
            return {
                'left': left,
                'top': top,
                'width': self.width,
                'height': self.height
            }
            
        except Exception as e:
            self.recording = False
            print(f"Recording error: {str(e)}")
            traceback.print_exc()
            messagebox.showerror("Error", f"Recording error: {str(e)}")
            return None

    def stop_recording(self):
        if self.recording:
            self.recording = False
            if self.process:
                try:
                    self.process.communicate(input=b'q', timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                except Exception as e:
                    print(f"Error stopping recording: {e}")
                    self.process.kill()
                    self.process.wait()
            
            # 移除边框窗口
            if hasattr(self, 'border_hwnd') and self.border_hwnd:
                try:
                    win32gui.DestroyWindow(self.border_hwnd)
                    self.border_hwnd = None
                except Exception as e:
                    print(f"Error destroying border window: {e}")

class RecordingPathManager:
    def __init__(self):
        self.username = getpass.getuser()
        self.base_dir = os.path.join("C:", os.sep, "Users", self.username, ".rec")
        self.timestamp = None
        
        # 确保目录存在
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
    
    def initialize_timestamp(self):
        """初始化时间戳，确保所有文件使用相同的时间戳"""
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.timestamp
    
    def get_audio_filename(self, is_input=False, device_name=None):
        """生成音频文件名"""
        if is_input:
            return os.path.join(self.base_dir, 
                f"{self.timestamp}_audio_in.wav")
        else:
            # 清理设备名中的特殊字符
            if device_name:
                device_name = "".join(c for c in device_name if c.isalnum() or c in (' ', '-', '_'))
                device_name = device_name.strip()
            return os.path.join(self.base_dir, 
                f"{self.timestamp}_audio_out_{device_name}.wav")
    
    def get_video_filename(self):
        """生成视频文件名"""
        return os.path.join(self.base_dir, 
            f"{self.timestamp}_video.mp4")
    
    def get_merged_filename(self):
        """生成合成文件名"""
        return os.path.join(self.base_dir, 
            f"{self.timestamp}_merge.mp4")

class RecorderUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("FastShot Recorder")
        self.window.geometry("400x600")
        self.window.resizable(False, False)
        
        # 获取屏幕信息
        self.monitors = ScreenInfo.get_real_resolution()
        
        self.recorder = None
        self.recording = False
        self.start_time = None
        self.update_thread = None
        
        # 初始化音频录制管理器
        self.audio_manager = AudioRecorderManager()
        self.selected_output_devices = []
        self.selected_input_device = None
        
        self.path_manager = RecordingPathManager()
        
        self.setup_ui()
        
    def setup_ui(self):
        # 质量选择
        quality_frame = ttk.LabelFrame(self.window, text="录制质量", padding=10)
        quality_frame.pack(fill="x", padx=10, pady=5)
        
        self.quality_var = tk.IntVar(value=3)
        qualities = [("最低质量 (最小文件)", 1),
                    ("低质量", 2),
                    ("中等质量", 3),
                    ("高质量", 4),
                    ("最高质量", 5)]
                    
        for text, value in qualities:
            ttk.Radiobutton(quality_frame, text=text, value=value, 
                           variable=self.quality_var).pack(anchor="w")
        
        # 添加音频设备选择区域
        audio_frame = ttk.LabelFrame(self.window, text="音频设备", padding=10)
        audio_frame.pack(fill="x", padx=10, pady=5)
        
        # 输出设备列表框
        ttk.Label(audio_frame, text="输出设备:").pack(anchor="w")
        self.output_listbox = tk.Listbox(audio_frame, selectmode=tk.MULTIPLE, height=4)
        self.output_listbox.pack(fill="x", pady=2)
        
        # 输入设备下拉框
        ttk.Label(audio_frame, text="输入设备:").pack(anchor="w")
        self.input_combo = ttk.Combobox(audio_frame, state="readonly")
        self.input_combo.pack(fill="x", pady=2)
        
        # 刷新音频设备按钮
        refresh_audio_btn = ttk.Button(audio_frame, text="刷新音频设备",
                                     command=self.refresh_audio_devices)
        refresh_audio_btn.pack(pady=2)
        
        # 初始化音频设备列表
        self.refresh_audio_devices()
        
        # 状态显示区域
        status_frame = ttk.LabelFrame(self.window, text="录制状态", padding=10)
        status_frame.pack(fill="x", padx=10, pady=5)
        
        # 使用网格局来标
        self.status_labels = {}
        status_items = [
            ("time", "录制时间: 00:00:00"),
            ("size", "文件大小: 0 MB"),
            ("fps", "帧率: 0 fps"),
            ("resolution", "分辨率: -"),
        ]
        
        for i, (key, text) in enumerate(status_items):
            ttk.Label(status_frame, text=text).grid(row=i, column=0, sticky="w", pady=2)
            self.status_labels[key] = ttk.Label(status_frame, text="")
            self.status_labels[key].grid(row=i, column=1, sticky="w", pady=2)
        
        # 控制按钮
        control_frame = ttk.Frame(self.window)
        control_frame.pack(fill="x", padx=10, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="开始录制", 
                                     command=self.start_recording)
        self.start_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="停止录制", 
                                    command=self.stop_recording, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.window, variable=self.progress_var, 
                                      maximum=100)
        self.progress.pack(fill="x", padx=10, pady=5)

    def refresh_audio_devices(self):
        """刷新音频设备列表"""
        try:
            print("\n[Audio] Refreshing audio devices...")
            # 清空现有列表
            self.output_listbox.delete(0, tk.END)
            self.input_combo.set('')
            
            # 获取设备列表
            output_devices, input_devices = self.audio_manager.get_available_devices()
            
            print(f"[Audio] Found {len(output_devices)} output devices and {len(input_devices)} input devices")
            
            # 添加输出设备
            self.output_devices = output_devices
            default_index = None
            for i, device in enumerate(output_devices):
                print(f"[Audio] Output device: {device['name']} {'(Default)' if device.get('is_default') else ''}")
                self.output_listbox.insert(tk.END, device['name'])
                if device.get('is_default'):
                    default_index = i
            
            # 选中默认设备
            if default_index is not None:
                self.output_listbox.selection_set(default_index)
                print(f"[Audio] Selected default output device at index {default_index}")
            
            # 添加输入设备
            self.input_devices = input_devices
            self.input_combo['values'] = [''] + [dev['name'] for dev in input_devices]
            for device in input_devices:
                print(f"[Audio] Input device: {device['name']}")
            self.input_combo.set('')  # 设置为空选项
            
        except Exception as e:
            print(f"[Audio] Error refreshing devices: {str(e)}")
            traceback.print_exc()
            messagebox.showerror("错误", f"刷音频设备失败: {str(e)}")
    
    def start_recording(self):
        try:
            # 初始化时间戳
            self.path_manager.initialize_timestamp()
            
            # 初始化录屏器
            self.recorder = ScreenRecorder(quality=self.quality_var.get())
            
            # 获取选中的音频设备（但暂时不开始录制）
            selected_outputs = []
            for i in self.output_listbox.curselection():
                selected_outputs.append(self.output_devices[i])
            
            selected_input = None
            input_name = self.input_combo.get()
            if input_name:
                for device in self.input_devices:
                    if device['name'] == input_name:
                        selected_input = device
                        break
            
            # 准备录制文件名
            video_filename = self.path_manager.get_video_filename()
            self.current_video_file = video_filename  # 移到这里
            self.current_audio_files = []  # 初始化为空列表
            
            # 先隐藏主窗口
            self.window.withdraw()
            
            # 更新按钮状态
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            
            # 开始录制
            self.recording = True
            self.start_time = time.time()
            
            # 创建选择窗口并等待用户选择区域
            select_window = tk.Toplevel()
            select_window.attributes('-alpha', 0.3)
            select_window.attributes('-topmost', True)
            
            # 获取所有显示器的总边界
            min_x = min(m['x'] for m in self.monitors)
            min_y = min(m['y'] for m in self.monitors)
            max_x = max(m['x'] + m['width'] for m in self.monitors)
            max_y = max(m['y'] + m['height'] for m in self.monitors)
            
            total_width = max_x - min_x
            total_height = max_y - min_y
            
            # 设置窗口位置和大小，确保覆盖所有显示器
            select_window.geometry(f"{total_width}x{total_height}+{min_x}+{min_y}")
            
            # 移除窗口的标题和边框
            select_window.overrideredirect(True)
            
            canvas = tk.Canvas(select_window, cursor="cross", highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)
            
            # 绘制显示器边界（可选，帮助用户识别显示器位置）
            for monitor in self.monitors:
                x = monitor['x'] - min_x
                y = monitor['y'] - min_y
                w = monitor['width']
                h = monitor['height']
                canvas.create_rectangle(x, y, x+w, y+h, outline='gray', dash=(2, 2))

            start_x = start_y = end_x = end_y = 0
            rect_id = None
            drawing = False

            def on_press(event):
                nonlocal start_x, start_y, drawing, rect_id
                start_x, start_y = event.x_root, event.y_root
                drawing = True
                if rect_id:
                    canvas.delete(rect_id)
                # 转换坐标到画布坐标系
                canvas_x = event.x_root - min_x
                canvas_y = event.y_root - min_y
                rect_id = canvas.create_rectangle(
                    canvas_x, canvas_y, canvas_x, canvas_y,
                    outline='red', width=2
                )

            def on_motion(event):
                nonlocal rect_id
                if drawing:
                    if rect_id:
                        canvas.delete(rect_id)
                    # 转换坐标到画布坐标系
                    canvas_start_x = start_x - min_x
                    canvas_start_y = start_y - min_y
                    canvas_current_x = event.x_root - min_x
                    canvas_current_y = event.y_root - min_y
                    rect_id = canvas.create_rectangle(
                        canvas_start_x, canvas_start_y,
                        canvas_current_x, canvas_current_y,
                        outline='red', width=2
                    )

            def on_release(event):
                nonlocal end_x, end_y, drawing
                end_x, end_y = event.x_root, event.y_root
                drawing = False
                select_window.destroy()
                # 显示主窗口
                self.window.deiconify()
                
                try:
                    # 开始视频录制并获取录制区域信息
                    recording_area = self.recorder.start_recording(start_x, start_y, end_x, end_y)
                    
                    if recording_area:
                        # 在这里开始音频录制
                        if selected_outputs or selected_input:  # 只在有选择设备时尝试录制音频
                            try:
                                audio_files = self.audio_manager.start_recording(
                                    selected_outputs=selected_outputs,
                                    selected_input=selected_input,
                                    path_manager=self.path_manager  # 传递path_manager
                                )
                                if audio_files:
                                    self.current_audio_files = audio_files
                            except Exception as e:
                                print(f"音频录制初始化失败: {str(e)}")
                                traceback.print_exc()
                                # 音频失败不影响视频录制继续
                        
                        # 显示边框
                        self.recorder.show_recording_border(
                            recording_area['left'],
                            recording_area['top'],
                            recording_area['width'],
                            recording_area['height'],
                            self.window
                        )
                        
                        # 启动状态更新线程
                        self.update_thread = threading.Thread(target=self.update_status)
                        self.update_thread.daemon = True
                        self.update_thread.start()
                except Exception as e:
                    print(f"录制启动失败: {str(e)}")
                    traceback.print_exc()
                    self.stop_recording()  # 确保清理资源
                    messagebox.showerror("错误", f"录制启动失败: {str(e)}")

            # 添加退出快捷键
            def on_escape(event):
                select_window.destroy()
                self.window.deiconify()
                self.start_button.config(state="normal")
                self.stop_button.config(state="disabled")
                self.recording = False

            canvas.bind("<Button-1>", on_press)
            canvas.bind("<B1-Motion>", on_motion)
            canvas.bind("<ButtonRelease-1>", on_release)
            select_window.bind("<Escape>", on_escape)
            
        except Exception as e:
            messagebox.showerror("错误", f"开始录制失败: {str(e)}")
    
    def stop_recording(self):
        try:
            print("正在停止录制...")
            
            # 停止录制标志
            self.recording = False  # 这会让状态更新线程停止
            
            # 停止视频录制
            video_file = None
            if self.recorder:
                video_file = self.recorder.output_file
                self.recorder.stop_recording()
                print("视频录制已停止")
            
            # 停止音频录制（如果有的话）
            if hasattr(self, 'audio_manager') and hasattr(self, 'current_audio_files') and self.current_audio_files:
                self.audio_manager.stop_recording()
                print("音频录制已停止")
                
                # 等待确保视频文件已经完全保存
                if video_file:
                    max_wait = 10  # 最多等待10秒
                    wait_time = 0
                    while not os.path.exists(video_file) and wait_time < max_wait:
                        print(f"等待视频文件生成: {video_file}")
                        time.sleep(1)
                        wait_time += 1
                    
                    if not os.path.exists(video_file):
                        raise Exception(f"视频文件未能在{max_wait}秒内生成")
                    
                    # 等待文件大小稳定（确保写入完成）
                    last_size = -1
                    current_size = os.path.getsize(video_file)
                    while last_size != current_size and wait_time < max_wait:
                        time.sleep(0.5)
                        last_size = current_size
                        current_size = os.path.getsize(video_file)
                        wait_time += 0.5
                        print(f"等待视频文件写入完成: {current_size} bytes")
                
                # 如果有音频，合并音视频
                print("开始合并音视频...")
                self.merge_audio_video()
            else:
                print("没有音频需要处理，录制完成")
            
            # 等待状态更新线程结束
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join(timeout=2)  # 等待最多2秒
            
            # 更新按钮状态
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            
            # 重置状态显示
            self.reset_status()
            
        except Exception as e:
            error_msg = f"停止录制失败: {str(e)}"
            print(error_msg)
            messagebox.showerror("错误", error_msg)
    
    def merge_audio_video(self):
        """合并音频和视频文件"""
        try:
            video_file = self.recorder.output_file
            merged_file = self.path_manager.get_merged_filename()
            
            # 构建 FFmpeg 命令
            cmd = ['ffmpeg', '-y']  # -y 覆盖已存在的文件
            
            # 添加视频输入
            cmd.extend(['-i', video_file])
            
            # 添加所有音频输入
            for audio_file in self.current_audio_files:
                cmd.extend(['-i', audio_file])
            
            # 添加混音参数
            filter_complex = []
            for i in range(len(self.current_audio_files)):
                filter_complex.append(f'[{i+1}:a]')
            
            if filter_complex:
                filter_str = f"{''.join(filter_complex)}amix=inputs={len(self.current_audio_files)}:duration=longest[aout]"
                cmd.extend([
                    '-filter_complex', filter_str,
                    '-map', '0:v',
                    '-map', '[aout]'
                ])
            
            # 添加输出参数
            cmd.extend([
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                merged_file
            ])
            
            print("执行FFmpeg命令:", ' '.join(cmd))
            
            # 执行合并命令
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"音视频合并成功: {merged_file}")
                self.show_completion_dialog(merged_file)
            else:
                raise Exception(f"FFmpeg 返回错误: {result.stderr}")
            
        except Exception as e:
            error_msg = f"合并音视频失败: {str(e)}"
            print(error_msg)
            if hasattr(e, 'stderr'):
                print("FFmpeg错误输出:", e.stderr)
            messagebox.showerror("错误", error_msg)
    
    def update_status(self):
        def update_ui(time_str, size_str, res_str, fps_str):
            """在主线程中更新UI的辅助函数"""
            try:
                if not self.recording:  # 如果录制已停止，不再更新UI
                    return
                self.status_labels["time"].config(text=time_str)
                self.status_labels["size"].config(text=size_str)
                self.status_labels["resolution"].config(text=res_str)
                self.status_labels["fps"].config(text=fps_str)
            except Exception as e:
                print(f"UI update error: {e}")

        try:
            while self.recording:  # 检查录制状态
                if self.recorder and self.recorder.output_file:
                    # 1. 更新录制时间
                    elapsed = time.time() - self.start_time
                    hours = int(elapsed // 3600)
                    minutes = int((elapsed % 3600) // 60)
                    seconds = int(elapsed % 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    
                    # 2. 获取当前文件大小
                    size_str = "0 B"
                    try:
                        if os.path.exists(self.recorder.output_file):
                            size = os.path.getsize(self.recorder.output_file)
                            size_str = humanize.naturalsize(size)
                            # print(f"Debug - Current file size: {size} bytes ({size_str})")  # 调试输出
                    except Exception as e:
                        print(f"Error getting file size: {e}")
                    
                    # 3. 获取当前分辨率
                    res_str = f"{self.recorder.width}x{self.recorder.height}"
                    
                    # 4. 获取当前帧率
                    fps_str = f"{self.recorder.fps} fps"
                    
                    # 5. 在主线程中更新UI
                    if self.recording:  # 再次检查录制状态
                        self.window.after(1, update_ui, time_str, size_str, res_str, fps_str)
                
                # 6. 等待一小段时间后再次更新
                time.sleep(0.5)
            
            print("状态更新线程已停止")
            
        except Exception as e:
            print(f"Status update error: {e}")
            traceback.print_exc()

    def reset_status(self):
        for label in self.status_labels.values():
            label.config(text="")
        self.progress_var.set(0)

    def run(self):
        self.window.mainloop()

    def show_completion_dialog(self, filepath):
        """显示录制完成对话框"""
        dialog = tk.Toplevel(self.window)
        dialog.title("完成")
        dialog.geometry("500x150")
        dialog.resizable(False, False)
        
        # 文件路径标签
        path_label = ttk.Label(dialog, 
            text=f"录制已完成并保存为:\n{filepath}", 
            wraplength=450)
        path_label.pack(pady=10)
        
        def copy_path():
            """复制路径到剪贴板"""
            dialog.clipboard_clear()
            dialog.clipboard_append(filepath)
            dialog.update()
            messagebox.showinfo("提示", "路径已复制到剪贴板")
        
        # 按钮框架
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        # 复制按钮
        copy_btn = ttk.Button(button_frame, 
            text="复制路径", 
            command=copy_path)
        copy_btn.pack(side="left", padx=5)
        
        # 确定按钮
        ok_btn = ttk.Button(button_frame, 
            text="确定", 
            command=dialog.destroy)
        ok_btn.pack(side="left", padx=5)
        
        # 使对话框居中
        dialog.transient(self.window)
        dialog.grab_set()
        
        # 计算居中位置
        window_x = self.window.winfo_x()
        window_y = self.window.winfo_y()
        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()
        
        dialog_width = 500
        dialog_height = 150
        
        x = window_x + (window_width - dialog_width) // 2
        y = window_y + (window_height - dialog_height) // 2
        
        dialog.geometry(f"+{x}+{y}")
        
        # 等待对话框关闭
        self.window.wait_window(dialog)

if __name__ == '__main__':
    ui = RecorderUI()
    ui.run()