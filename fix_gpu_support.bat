@echo off
echo ========================================
echo 修復 NVIDIA GPU 支持
echo ========================================
echo.

echo [1/3] 卸載現有的 PyTorch (CPU 版本)...
pip uninstall -y torch torchvision torchaudio

echo.
echo [2/3] 安裝 PyTorch (CUDA 12.1 版本)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo.
echo [3/3] 驗證安裝...
python -c "import torch; print(''); print('='*50); print(f'PyTorch 版本: {torch.__version__}'); print(f'CUDA 可用: {torch.cuda.is_available()}'); if torch.cuda.is_available(): print(f'GPU 名稱: {torch.cuda.get_device_name(0)}'); print('='*50)"

echo.
echo 完成！如果看到 "CUDA 可用: True"，則安裝成功。
pause
