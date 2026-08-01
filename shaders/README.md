# MPV 用户着色器目录

本目录用于存放 GLSL 着色器文件（`.glsl` 或 `.hook`），供 MPV 播放器加载使用。

## 支持的着色器预设

应用内置以下预设名称，会自动在此目录中查找匹配的文件：

| 预设名      | 说明                          | 推荐文件名                    |
|------------|------------------------------|------------------------------|
| `ravu`     | RAVU 锐利放大                  | `ravu_r3.hook`               |
| `fsrcnnx`  | FSRCNNX 超分辨率               | `FSRCNNX_x2_8-0-4-1.glsl`   |
| `anime4k`  | Anime4K 动画增强              | `Anime4K_Clamp_Highlights.hook` |
| `krig`     | KrigBilateral 色度升频        | `KrigBilateral.hook`         |
| `ssim`     | SSimDownscaler 高质量降频     | `SSimDownscaler.hook`        |

## 文件查找规则

1. 精确匹配：`预设名.glsl` 或 `预设名.hook`
2. 前缀匹配：以预设名开头的 `.glsl` 或 `.hook` 文件

例如：`ravu` 预设会依次查找 `ravu.glsl`、`ravu.hook`，然后查找 `ravu_r3.hook` 等。

## 去哪里下载着色器

以下是一些常用的着色器下载来源：

- **MPV 官方着色器集合**：https://github.com/bloc97/Anime4K
- **mpv-config 着色器**：https://github.com/mpv-player/mpv/wiki/User-Scripts
- **glsl-shaders 整合包**：https://github.com/igv/FSRCNN-TensorFlow/releases
- **KrigBilateral / SSimDownscaler**：https://github.com/igv/Inpaint-OpenGL

下载后将 `.glsl` 或 `.hook` 文件放入本目录即可。

## 注意事项

- 着色器在 GPU 渲染管线运行，不需要 copy-back 硬件解码
- 多个着色器可以通过 MPV 的 `glsl-shaders` 属性用逗号分隔加载
- 着色器性能取决于 GPU，低端 GPU 可能导致帧率下降
- Android 端着色器目录为 `app filesDir/shaders/`
