from PIL import Image

# 打开 PNG 图像
png_image = Image.open('D:\\icon\\mp3.png')

# 保存为 ICO 格式
png_image.save('D:\\icon\\mp3.ico')
