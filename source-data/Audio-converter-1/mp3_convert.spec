# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 注意：这个 spec 文件是为 PyInstaller 4.0 或更高版本编写的

a = Analysis(['MP3_Convert.py'],
             pathex=['path/to/your/python/script'],
             binaries=[('C:\\Program Files\\FFMPEG\\bin\\ffmpeg.exe', 'ffmpeg')],  # 将 ffmpeg.exe 添加到可执行文件列表中
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='MP3_Convert',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True, icon='D:\\icon\\mp3.png')  # 可以添加一个图标文件

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='MP3_Convert')
