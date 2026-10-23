"""Read-only preflight: no GUI, singleton, credential or account access."""
from pathlib import Path
import importlib.util
import json
import sys

BASE = Path(__file__).resolve().parent

def check():
    problems = []
    if sys.platform != 'win32':
        problems.append('仅支持 Windows x64')
    for module in ('clr', 'webview'):
        if importlib.util.find_spec(module) is None:
            problems.append('缺少 Python 依赖：' + module + '；运行 安装依赖.cmd')
    spec = importlib.util.find_spec('webview')
    if spec and spec.origin:
        lib = Path(spec.origin).parent / 'lib'
        for name in ('Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll', 'runtimes/win-x64/native/WebView2Loader.dll'):
            if not (lib/name).is_file():
                problems.append('pywebview 缺少运行库：' + name)
    for name in ('pixi-v6.min.js', 'pixi-live2d-display-cubism4.min.js', 'live2dcubismcore.min.js'):
        if not (BASE/'web/lib'/name).is_file():
            problems.append('缺少 web/lib/' + name + '；见 README 第三方组件安装')
    model = BASE/'web/model/settings.json'
    if not model.is_file():
        problems.append('模型不存在：请按 README 放入您有权使用的 Cubism 模型及 settings.json')
    else:
        try:
            data=json.loads(model.read_text(encoding='utf-8-sig'))
            refs=data.get('FileReferences') or {}
            files=[refs.get('Moc')] + list(refs.get('Textures') or [])
            if not refs.get('Moc') or not refs.get('Textures'):
                problems.append('模型 settings.json 必须含 FileReferences.Moc / Textures')
            for name in filter(None,files):
                target=(model.parent/name).resolve()
                if not target.is_relative_to(model.parent.resolve()) or not target.is_file():
                    problems.append('模型引用无效或文件缺失：' + str(name))
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            problems.append('模型 settings.json 格式错误：' + type(exc).__name__)
    return problems

if __name__ == '__main__':
    problems=check()
    print('\n'.join(problems) if problems else '启动文件检查通过；仍需 WebView2 Runtime 和可用图形驱动。')
    raise SystemExit(2 if problems else 0)
