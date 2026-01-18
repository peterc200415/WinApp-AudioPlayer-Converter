# GPU 問題診斷與修復指南

## 🔍 問題診斷結果

**問題**：NVIDIA GPU 未在轉錄時運作

**根本原因**：安裝的是 **PyTorch CPU 版本**（`2.9.1+cpu`），而不是 CUDA 版本

**當前狀態**：
- PyTorch 版本：`2.9.1+cpu` ❌
- CUDA 可用：`False` ❌
- GPU 數量：`0` ❌

---

## ✅ 解決方案

### 步驟 1：卸載現有的 PyTorch（CPU 版本）

```bash
pip uninstall torch torchvision torchaudio
```

### 步驟 2：安裝 CUDA 版本的 PyTorch

根據您的 CUDA 版本選擇對應的安裝命令：

#### 檢查 CUDA 版本
```bash
nvidia-smi
```
查看 "CUDA Version" 行（例如：12.1, 11.8）

#### 安裝對應的 PyTorch

**CUDA 11.8：**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**CUDA 12.1：**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**CUDA 12.4：**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

**最新穩定版（推薦）：**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 步驟 3：驗證安裝

```bash
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

**預期輸出：**
```
PyTorch: 2.x.x+cu121  (注意：應該有 +cu121 等 CUDA 標記)
CUDA available: True
GPU: NVIDIA GeForce RTX 3080 (或您的 GPU 型號)
```

---

## 🛠️ 自動安裝腳本

我也可以為您創建一個自動檢測和安裝的腳本。

---

## ⚠️ 注意事項

1. **CUDA 驅動**：確保已安裝 NVIDIA 驅動程式
   - 檢查：`nvidia-smi` 應該能正常運行
   - 如果沒有，請從 NVIDIA 官網下載安裝

2. **版本匹配**：
   - PyTorch CUDA 版本不需要完全匹配系統 CUDA 版本
   - PyTorch 自帶 CUDA runtime
   - 建議使用 CUDA 11.8 或 12.1（最兼容）

3. **Whisper 依賴**：
   - 安裝 CUDA 版本的 PyTorch 後，Whisper 會自動使用 GPU
   - 無需重新安裝 whisper 套件

---

## 🔄 安裝後的行為變化

安裝 CUDA 版本後：
- ✅ `torch.cuda.is_available()` 會返回 `True`
- ✅ `_get_device()` 會自動選擇 `"cuda"`
- ✅ Whisper 模型會自動載入到 GPU
- ✅ 轉錄速度會大幅提升（10-50x）

---

## 📊 性能對比

| 設備 | 10分鐘音頻轉錄時間 |
|------|-------------------|
| CPU | 5-10 分鐘 |
| NVIDIA GPU (CUDA) | 10-60 秒 |

---

## 💡 如果還有問題

如果安裝後仍有問題，請檢查：

1. **NVIDIA 驅動**：
   ```bash
   nvidia-smi
   ```

2. **PyTorch 是否正確安裝**：
   ```bash
   python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
   ```

3. **應用程式日誌**：
   查看轉錄時的控制台輸出，應該看到：
   ```
   載入 Whisper 模型: base, 設備: cuda
   ```
