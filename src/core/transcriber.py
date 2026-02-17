"""
語音轉錄器模組
使用 Whisper 模型進行音頻轉錄
"""

import os
import warnings
from typing import Any, Callable, Dict, List, Optional

import torch
import whisper
from threading import Lock

from src.core.subtitle_parser import Subtitle
from src.utils.time_utils import format_time


class Transcriber:
    """語音轉錄器類（單例模式）"""
    
    _instance: Optional['Transcriber'] = None
    _lock = Lock()
    
    def __new__(cls):
        """實現單例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化轉錄器"""
        if hasattr(self, '_initialized'):
            return
        
        self._model: Optional[whisper.Whisper] = None
        self._model_name: Optional[str] = None
        self._device: Optional[str] = None
        self.on_info: Optional[Callable[[str], None]] = None
        self._model_load_lock = Lock()
        self._disable_cuda: bool = False
        self._warned_cpu_build: bool = False
        self._warned_cuda_disabled: bool = False
        self._warned_cuda_unavailable: bool = False
        self._warned_arch_unsupported: bool = False
        self._initialized = True

    def _emit_info(self, message: str) -> None:
        """Emit info message to console and optional UI callback."""
        print(message)
        if self.on_info:
            try:
                self.on_info(message)
            except Exception:
                pass
    
    def _get_device(self, device_preference: str = "auto") -> str:
        """
        確定使用的設備（GPU 或 CPU）
        
        Args:
            device_preference: 設備偏好 ("auto", "cuda", "cpu")
                - auto: GPU-first（如果可用則使用 CUDA，否則使用 CPU）
        
        Returns:
            設備名稱
        """
        with warnings.catch_warnings():
            # Suppress noisy warnings for unsupported/legacy GPUs on newer torch builds
            warnings.filterwarnings(
                "ignore",
                category=UserWarning,
                module=r"torch\.cuda",
            )
            cuda_available = torch.cuda.is_available() and (not self._disable_cuda)
        
        # 診斷資訊
        if device_preference in ("auto", "cuda") and not cuda_available:
            # 檢查是否安裝了 CPU 版本的 PyTorch
            if "+cpu" in torch.__version__:
                if not self._warned_cpu_build:
                    self._emit_info(f"[WARN] Detected PyTorch CPU build ({torch.__version__})")
                    self._emit_info("       Install a CUDA build to enable GPU acceleration")
                    self._emit_info("       Run: pip uninstall torch torchvision torchaudio")
                    self._emit_info("       Then: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
                    self._warned_cpu_build = True
            else:
                if self._disable_cuda:
                    # Already warned about incompatibility; keep subsequent fallbacks silent.
                    self._warned_cuda_disabled = True
                else:
                    if not self._warned_cuda_unavailable:
                        self._emit_info("[WARN] CUDA not available; falling back to CPU")
                        self._warned_cuda_unavailable = True
        
        if device_preference == "cpu":
            return "cpu"

        # cuda / auto 都採用 GPU-first：CUDA 可用就用 CUDA，否則退回 CPU
        if cuda_available:
            # Check whether this PyTorch build supports the GPU architecture
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        category=UserWarning,
                        module=r"torch\.cuda",
                    )
                    major, minor = torch.cuda.get_device_capability(0)
                    arch = f"sm_{major}{minor}"
                    supported_arches = set(torch.cuda.get_arch_list())
                if supported_arches and arch not in supported_arches:
                    gpu_name = torch.cuda.get_device_name(0)
                    if not self._warned_arch_unsupported:
                        self._emit_info(
                            f"[WARN] GPU arch {arch} ({gpu_name}) is not supported by this PyTorch build; falling back to CPU"
                        )
                        self._warned_arch_unsupported = True
                    self._disable_cuda = True
                    return "cpu"
            except Exception:
                # If any capability query fails, still try CUDA; load_model() has a safe fallback.
                pass

            gpu_name = torch.cuda.get_device_name(0)
            self._emit_info(f"[OK] Using GPU: {gpu_name}")
            return "cuda"

        return "cpu"
    
    def load_model(self, model_name: str = "base", device: str = "auto") -> None:
        """
        載入 Whisper 模型
        
        Args:
            model_name: 模型名稱 (tiny, base, small, medium, large)
            device: 設備 ("auto", "cuda", "cpu")
        """
        resolved_device = self._get_device(device)

        with self._model_load_lock:
            if (
                self._model is not None
                and self._model_name == model_name
                and self._device == resolved_device
            ):
                return  # 模型已載入且設備一致

            self._device = resolved_device
            self._emit_info(f"Loading Whisper model: {model_name}, device: {self._device}")

            try:
                self._model = whisper.load_model(model_name, device=self._device)
                self._model_name = model_name
                return
            except Exception as e:
                # GPU-first auto mode: if CUDA fails at runtime (unsupported GPU arch / driver), fallback to CPU
                msg = str(e)
                cuda_kernel_image_error = (
                    "no kernel image is available for execution on the device" in msg
                    or "cudaErrorNoKernelImageForDevice" in msg
                )
                if self._device == "cuda" and (device in ("auto", "cuda")) and cuda_kernel_image_error:
                    self._emit_info("[WARN] CUDA runtime not compatible with this GPU; fallback to CPU")
                    self._disable_cuda = True
                    try:
                        torch.cuda.empty_cache()
                    except Exception:
                        pass

                    self._device = "cpu"
                    self._emit_info(f"Loading Whisper model: {model_name}, device: {self._device}")
                    self._model = whisper.load_model(model_name, device=self._device)
                    self._model_name = model_name
                    return
                raise
    
    def transcribe(
        self,
        audio_path: str,
        model_name: str = "base",
        device: str = "auto",
        **transcribe_options: Any,
    ) -> Dict:
        """
        轉錄音頻檔案
        
        Args:
            audio_path: 音頻檔案路徑
            model_name: 模型名稱
            device: 設備偏好
        
        Returns:
            Whisper 轉錄結果字典
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音頻檔案不存在: {audio_path}")
        
        self.load_model(model_name, device)
        
        if self._model is None:
            raise RuntimeError("模型未載入")
        
        # Avoid CPU FP16 warning, and suppress "CPU when CUDA available" noise
        use_fp16 = self._device == "cuda"
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"Performing inference on CPU when CUDA is available",
            )
            result = self._model.transcribe(audio_path, fp16=use_fp16, **transcribe_options)
        return result

    def transcribe_to_subtitles(
        self,
        audio_path: str,
        model_name: str = "base",
        device: str = "auto",
        **transcribe_options: Any,
    ) -> List[Subtitle]:
        """轉錄音頻並回傳字幕列表（不寫入檔案）"""
        result = self.transcribe(audio_path, model_name, device, **transcribe_options)

        subtitles: List[Subtitle] = []
        for i, segment in enumerate(result.get("segments", []), start=1):
            try:
                start = float(segment.get("start", 0.0))
                end = float(segment.get("end", 0.0))
                text = str(segment.get("text", "")).strip()
            except Exception:
                continue

            if not text:
                continue

            subtitles.append(
                Subtitle(
                    index=i,
                    start_time=start,
                    end_time=end,
                    text=text,
                )
            )

        return subtitles
    
    def transcribe_to_srt(self, audio_path: str, output_path: Optional[str] = None,
                          model_name: str = "base", device: str = "auto") -> str:
        """
        轉錄音頻並保存為 SRT 檔案
        
        Args:
            audio_path: 音頻檔案路徑
            output_path: 輸出 SRT 檔案路徑，如果為 None 則自動生成
            model_name: 模型名稱
            device: 設備偏好
        
        Returns:
            輸出的 SRT 檔案路徑
        """
        if output_path is None:
            base_path = os.path.splitext(audio_path)[0]
            output_path = f"{base_path}.srt"
        
        result = self.transcribe(audio_path, model_name, device)
        
        with open(output_path, 'w', encoding='utf-8') as srt_file:
            for i, segment in enumerate(result["segments"], start=1):
                start = segment["start"]
                end = segment["end"]
                text = segment["text"].strip()
                start_time_str = format_time(start)
                end_time_str = format_time(end)
                srt_file.write(f"{i}\n{start_time_str} --> {end_time_str}\n{text}\n\n")
        
        return output_path
    
    @property
    def device(self) -> Optional[str]:
        """獲取當前使用的設備"""
        return self._device
    
    @property
    def model_name(self) -> Optional[str]:
        """獲取當前載入的模型名稱"""
        return self._model_name
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        獲取設備詳細資訊
        
        Returns:
            包含設備資訊的字典
        """
        info = {
            "pytorch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "current_device": self._device,
            "gpus": []
        }
        
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                gpu_info = {
                    "index": i,
                    "name": torch.cuda.get_device_name(i),
                    "memory_total_gb": torch.cuda.get_device_properties(i).total_memory / (1024**3),
                    "memory_allocated_gb": torch.cuda.memory_allocated(i) / (1024**3) if i == 0 else 0
                }
                info["gpus"].append(gpu_info)
        
        return info
