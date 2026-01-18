# GPU 平台支持評估與實現方案

## 📊 當前實現狀態

### 現有支持
- ✅ **NVIDIA GPU (CUDA)**：已實現，通過 `torch.cuda.is_available()` 檢測
- ✅ **CPU**：已實現，作為 fallback
- ❌ **AMD GPU (ROCm)**：未實現
- ❌ **Intel GPU**：未實現

### 當前代碼
```python
# src/core/transcriber.py (第 39-55 行)
def _get_device(self, device_preference: str = "auto") -> str:
    if device_preference == "cuda" and torch.cuda.is_available():
        return "cuda"
    elif device_preference == "cpu":
        return "cpu"
    else:
        return "cuda" if torch.cuda.is_available() else "cpu"
```

---

## 🎯 各平台實現難度評估

### 1. NVIDIA GPU (CUDA) ⭐ **簡單** ✅ 已完成

**難度**：低  
**現狀**：已完美支持

**優勢**：
- Whisper 原生支持 PyTorch + CUDA
- 驅動穩定，文檔完善
- 性能最佳（10-50x 加速 vs CPU）

**實現方式**：
```python
device = "cuda" if torch.cuda.is_available() else "cpu"
model = whisper.load_model("base", device=device)
```

---

### 2. AMD GPU (ROCm) ⭐⭐ **中等難度**

**難度**：中  
**現狀**：需要額外配置

**挑戰**：
1. **驅動安裝複雜**：ROCm 版本與 GPU 型號需匹配
2. **PyTorch 支援**：需要安裝 `torch-rocm` 版本（非官方預編譯版本）
3. **穩定性**：某些操作可能有 bug 或性能問題

**實現方式**：

#### 方案 A：PyTorch ROCm（推薦）
```python
# 需要安裝: pip install torch --index-url https://download.pytorch.org/whl/rocm5.6
if torch.version.cuda is None and hasattr(torch.version, 'hip'):
    device = "cuda"  # ROCm 使用 "cuda" 作為設備名稱
```

#### 方案 B：ONNX Runtime + ROCm
```python
import onnxruntime as ort
sess_options = ort.SessionOptions()
provider_options = [{'device_type': 'hip'}]  # ROCm backend
```

**工作量**：2-4 小時
- 檢測 ROCm 環境
- 安裝指導文檔
- 測試與驗證

---

### 3. Intel GPU ⭐⭐⭐ **較高難度**

**難度**：中高  
**現狀**：需要模型轉換

**挑戰**：
1. **模型格式轉換**：需要將 Whisper 轉為 ONNX 或 OpenVINO IR
2. **API 差異**：使用 OpenVINO 而非直接 PyTorch
3. **性能限制**：對大型模型可能不如 NVIDIA/AMD

**實現方式**：

#### 方案 A：OpenVINO（推薦 Intel Arc GPU）
```python
# 1. 轉換模型為 ONNX
# 2. 使用 OpenVINO Runtime
from openvino.runtime import Core

core = Core()
model = core.read_model("whisper.onnx")
compiled_model = core.compile_model(model, "GPU")  # Intel GPU
```

#### 方案 B：Intel Extension for PyTorch (IPEX)
```python
import intel_extension_for_pytorch as ipex
model = whisper.load_model("base")
model = ipex.optimize(model)
# 使用 xpu 設備
```

**工作量**：4-8 小時
- 模型轉換腳本
- OpenVINO 整合
- Intel GPU 檢測
- 性能優化

---

## 💡 推薦實現策略

### 階段一：增強現有實現（1-2 小時）

**目標**：改進設備檢測，支援多 GPU 選擇

**改進**：
1. 添加 GPU 資訊檢測（型號、記憶體）
2. 支援手動選擇 GPU（多 GPU 環境）
3. 更詳細的錯誤提示

**優點**：
- 保持簡單，不增加複雜度
- 改善 NVIDIA GPU 使用體驗
- 為未來擴展打下基礎

---

### 階段二：添加 AMD ROCm 支持（可選，2-4 小時）

**前提條件**：
- 用戶已安裝 ROCm 驅動
- 使用 PyTorch ROCm 版本

**實現**：
```python
def _detect_amd_gpu(self) -> bool:
    """檢測 AMD GPU (ROCm)"""
    try:
        # 檢查 ROCm 環境
        if hasattr(torch.version, 'hip') and torch.version.hip:
            return True
        # 或檢查環境變數
        import os
        if 'ROCM_HOME' in os.environ:
            return True
    except:
        pass
    return False
```

---

### 階段三：添加 Intel GPU 支持（可選，4-8 小時）

**前提條件**：
- 模型轉換為 ONNX
- 安裝 OpenVINO Toolkit

**實現**：
- 創建模型轉換工具
- 整合 OpenVINO Runtime
- 添加 Intel GPU 檢測

---

## 📋 建議的最終實現

### 推薦方案：優先支援 NVIDIA + 完善的 CPU Fallback

**原因**：
1. **覆蓋面廣**：NVIDIA GPU 佔據市場主導地位（約 80%+）
2. **穩定性高**：CUDA 支持最成熟
3. **開發成本低**：當前已實現，只需增強
4. **用戶體驗**：絕大多數用戶可立即受益

### 完整方案（進階）

如果未來要全面支援，建議採用**硬體抽象層**設計：

```
Transcriber (統一接口)
    ├─ CUDABackend (NVIDIA)
    ├─ ROCmBackend (AMD)
    ├─ OpenVINOBackend (Intel)
    └─ CPUBackend (Fallback)
```

**好處**：
- 模組化設計，易於擴展
- 每種後端獨立實現和測試
- 可選安裝（用戶只安裝需要的）

---

## 🔧 立即改進建議

### 改進 1：增強設備檢測（30 分鐘）

添加 GPU 資訊顯示，幫助用戶了解硬體狀態：

```python
def get_device_info(self) -> Dict[str, Any]:
    """獲取設備詳細資訊"""
    info = {
        "available_devices": [],
        "recommended_device": "cpu"
    }
    
    # 檢測 NVIDIA GPU
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            gpu_name = torch.cuda.get_device_name(i)
            gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
            info["available_devices"].append({
                "type": "NVIDIA CUDA",
                "name": gpu_name,
                "memory_gb": f"{gpu_memory:.1f}",
                "device_id": f"cuda:{i}"
            })
            info["recommended_device"] = f"cuda:{i}" if i == 0 else info["recommended_device"]
    
    # 檢測 CPU
    import psutil
    cpu_count = psutil.cpu_count()
    info["available_devices"].append({
        "type": "CPU",
        "name": f"CPU ({cpu_count} cores)",
        "device_id": "cpu"
    })
    
    return info
```

### 改進 2：配置選項增強（15 分鐘）

在配置中添加更詳細的設備選項：

```json
{
    "device": "auto",  // "auto", "cuda", "cuda:0", "cpu"
    "device_preference": {
        "primary": "cuda",
        "fallback": "cpu"
    }
}
```

---

## 📊 工作量總結

| 任務 | 難度 | 工作量 | 優先級 | 價值 |
|------|------|--------|--------|------|
| 增強 NVIDIA GPU 支持 | ⭐ | 1-2小時 | 高 | 高 |
| 添加 AMD ROCm 支持 | ⭐⭐ | 2-4小時 | 中 | 中 |
| 添加 Intel GPU 支持 | ⭐⭐⭐ | 4-8小時 | 低 | 低 |
| 硬體抽象層重構 | ⭐⭐⭐⭐ | 8-16小時 | 低 | 高（長期） |

---

## ✅ 結論

**當前建議**：
- ✅ **NVIDIA GPU**：已實現，只需增強
- ⚠️ **AMD GPU**：可選，需要用戶安裝 ROCm
- ⚠️ **Intel GPU**：可選，需要模型轉換

**實現難度排序**：
1. NVIDIA (CUDA) - 已完成 ✅
2. AMD (ROCm) - 中等 ⚠️
3. Intel (OpenVINO) - 較高 ⚠️

**總體評估**：
- **不困難**，但需要額外配置和測試
- 建議先完善 NVIDIA 支持，再逐步擴展
- 大多數用戶使用 NVIDIA GPU，優先支援最有價值
