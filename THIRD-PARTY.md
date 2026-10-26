# 第三方范围与归属

本副本只分发原项目自行编写的 Python、HTML、CSS、JavaScript 源码及模板文档/启动脚本。根目录 LICENSE 原样保留；其中的历史文件清单不是本模板实际携带组件的清单。原版权行含作者占位文字，本次未替换或虚构版权人。

| 使用时的组件 | 取得方式 | 许可范围 |
| --- | --- | --- |
| pythonnet 3.1.0、pywebview 6.2.1 及其传递依赖 | `pip install -r requirements.txt` | 各下载包自带许可证；非根目录 MIT 的重新授权 |
| Microsoft WebView2 .NET DLL / native loader | 由用户安装的 pywebview 包提供 | 微软条款；仓库无 DLL |
| Microsoft Edge WebView2 Runtime | 微软官网/用户系统 | 微软条款；仓库无 Runtime |
| PixiJS 6.5.10 | 用户从 npm 安装 `pixi.js@6.5.10` | MIT，保留上游版权与许可证 |
| pixi-live2d-display 0.4.0 | 用户从 npm 安装 | 适配器项目 MIT；打包 Cubism Framework 的部分另受其条款约束 |
| Live2D Cubism Core / Framework | 用户阅读 Live2D 官方许可后自行取得 | Live2D 对应许可，根目录 MIT 不覆盖 |
| 模型、贴图、表情、动作、角色图标 | 用户自行提供 | 由素材作者授权决定；仓库未附原素材 |

上游核对入口：

- [PixiJS v6.5.10 LICENSE](https://github.com/pixijs/pixijs/blob/v6.5.10/LICENSE)
- [pixi-live2d-display v0.4.0](https://github.com/guansss/pixi-live2d-display/tree/v0.4.0)
- [Live2D Cubism SDK for Web 官方下载与许可](https://www.live2d.com/en/sdk/download/web/)

本模板没有沿用旧说明中“Cubism Core 可以随本程序分发”的笼统判断。是否能再发布带模型/Core 的衍生包，须按实际取得的版本、组件许可和素材授权另行确认。

通用界面 SVG 及由其生成的 PNG 位于 web/banner-icons/，属于项目 UI 图形；不含角色插画。新增柔边仅使用 Windows System.Drawing，不引入新字体或图像库。
