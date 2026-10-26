"""A narrow alpha edge behind opaque native surfaces. Never participates in input.

The actual form and its Region remain untouched (especially WebView parents).
Uses existing System.Drawing; no polling, persistent bitmap, or screen capture.
"""
import ctypes,math
from ctypes import wintypes as W


def render_edge(size,surfaces,fill,scale=1):
    from System.Drawing import Bitmap,Graphics,Color,SolidBrush,Rectangle,GraphicsUnit
    from System.Drawing.Imaging import PixelFormat
    from System.Drawing.Drawing2D import SmoothingMode,InterpolationMode,PixelOffsetMode
    from pet_banner_style import rounded_path
    width,height=map(int,size);scale=max(1.,min(4.,float(scale)))
    pad=max(4,math.ceil(4*scale));factor=3
    large=Bitmap((width+2*pad)*factor,(height+2*pad)*factor,PixelFormat.Format32bppPArgb)
    g=None;result=None
    try:
        g=Graphics.FromImage(large)
        g.Clear(Color.Transparent);g.ScaleTransform(float(factor),float(factor))
        g.SmoothingMode=SmoothingMode.AntiAlias;g.PixelOffsetMode=PixelOffsetMode.HighQuality
        for (x,y,w,h),radius in surfaces:
            if w<=0 or h<=0:continue
            # A few low-alpha nested contours form a narrow soft falloff.
            for extent,alpha in ((2.5*scale,3),(1.9*scale,4),(1.35*scale,5),(.8*scale,7),(.55,210)):
                path=None;brush=None
                try:
                    path=rounded_path(x+pad-extent,y+pad-extent,w+2*extent,h+2*extent,radius+extent)
                    brush=SolidBrush(Color.FromArgb(alpha,*(fill if alpha==210 else (14,23,35))))
                    g.FillPath(brush,path)
                finally:
                    if brush is not None:brush.Dispose()
                    if path is not None:path.Dispose()
        result=Bitmap(width+2*pad,height+2*pad,PixelFormat.Format32bppPArgb)
        out=None
        try:
            out=Graphics.FromImage(result)
            out.Clear(Color.Transparent);out.InterpolationMode=InterpolationMode.HighQualityBicubic
            out.PixelOffsetMode=PixelOffsetMode.HighQuality
            out.DrawImage(large,Rectangle(0,0,result.Width,result.Height),Rectangle(0,0,large.Width,large.Height),GraphicsUnit.Pixel)
        finally:
            if out is not None:out.Dispose()
        return result,pad
    except Exception:
        if result is not None:result.Dispose()
        raise
    finally:
        if g is not None:g.Dispose()
        large.Dispose()


class _SIZE(ctypes.Structure):_fields_=[('cx',W.LONG),('cy',W.LONG)]
class _BLEND(ctypes.Structure):_fields_=[('op',W.BYTE),('flags',W.BYTE),('alpha',W.BYTE),('format',W.BYTE)]
class _HEADER(ctypes.Structure):
    _fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),('bits',W.WORD),('compression',W.DWORD),('bytes',W.DWORD),('x',W.LONG),('y',W.LONG),('used',W.DWORD),('important',W.DWORD)]
class _INFO(ctypes.Structure):_fields_=[('header',_HEADER),('colors',W.DWORD*3)]


class EdgeHalo:
    """One on-demand visual-only sibling beneath a target, disposed with it."""
    def __init__(self,target,scale=1,radius=24,provider=None,fill=None):
        self.target=target;self.scale=max(1.,float(scale));self.radius=radius*self.scale
        self.provider=provider;self.fill=fill;self.visual=None;self.hwnd=None
        self.closed=False;self.error=None;self._busy=False;self._key=None;self.pad=0
        self.render_count=0;self._topmost=None
        self._bindings=[('VisibleChanged',self.refresh),('SizeChanged',self.refresh),
                        ('BackColorChanged',self.refresh),('LocationChanged',self.move),
                        ('Activated',self.move),('FormClosed',self.dispose),('Disposed',self.dispose)]
        for name,fn in self._bindings:
            event=getattr(target,name);event+=fn
        if target.Visible:self.refresh()

    def _ensure(self):
        if self.hwnd:return
        from System.Windows.Forms import Form,FormBorderStyle
        v=Form();self.visual=v
        v.FormBorderStyle=getattr(FormBorderStyle,'None');v.ShowInTaskbar=False
        v.Text='Agent · 视觉柔边';v.MinimizeBox=False;v.MaximizeBox=False
        if self.target.Owner is not None:v.Owner=self.target.Owner
        self.hwnd=int(v.Handle.ToInt64())
        self.u=ctypes.WinDLL('user32',use_last_error=True);self.g=ctypes.WinDLL('gdi32',use_last_error=True)
        self.u.SetWindowPos.argtypes=[W.HWND,W.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,W.UINT];self.u.SetWindowPos.restype=W.BOOL
        self.u.ShowWindow.argtypes=[W.HWND,ctypes.c_int];self.u.ShowWindow.restype=W.BOOL
        self.u.GetDC.argtypes=[W.HWND];self.u.GetDC.restype=W.HDC
        self.u.ReleaseDC.argtypes=[W.HWND,W.HDC]
        self.u.UpdateLayeredWindow.argtypes=[W.HWND,W.HDC,ctypes.POINTER(W.POINT),ctypes.POINTER(_SIZE),W.HDC,ctypes.POINTER(W.POINT),W.DWORD,ctypes.POINTER(_BLEND),W.DWORD]
        self.u.UpdateLayeredWindow.restype=W.BOOL
        get=getattr(self.u,'GetWindowLongPtrW',self.u.GetWindowLongW);get.argtypes=[W.HWND,ctypes.c_int];get.restype=ctypes.c_ssize_t
        set_=getattr(self.u,'SetWindowLongPtrW',self.u.SetWindowLongW);set_.argtypes=[W.HWND,ctypes.c_int,ctypes.c_ssize_t];set_.restype=ctypes.c_ssize_t
        # Layered + transparent: Windows skips this entire visual for hit tests.
        required=0x80000|0x20|0x8000000|0x80
        set_(self.hwnd,-20,get(self.hwnd,-20)|required)
        if get(self.hwnd,-20)&required!=required:raise OSError('Visual edge input isolation unavailable')
        self.g.CreateCompatibleDC.argtypes=[W.HDC];self.g.CreateCompatibleDC.restype=W.HDC
        self.g.DeleteDC.argtypes=[W.HDC];self.g.DeleteDC.restype=W.BOOL
        self.g.CreateDIBSection.argtypes=[W.HDC,ctypes.POINTER(_INFO),W.UINT,ctypes.POINTER(ctypes.c_void_p),W.HANDLE,W.DWORD];self.g.CreateDIBSection.restype=W.HBITMAP
        self.g.SelectObject.argtypes=[W.HDC,W.HGDIOBJ];self.g.SelectObject.restype=W.HGDIOBJ
        self.g.DeleteObject.argtypes=[W.HGDIOBJ];self.g.DeleteObject.restype=W.BOOL

    def _upload(self,image):
        from System.Drawing import Rectangle
        from System.Drawing.Imaging import ImageLockMode,PixelFormat
        width,height=image.Width,image.Height
        data=image.LockBits(Rectangle(0,0,width,height),ImageLockMode.ReadOnly,PixelFormat.Format32bppPArgb)
        try:
            if data.Stride!=width*4:raise ValueError('Unexpected edge bitmap stride')
            raw=ctypes.string_at(int(data.Scan0.ToInt64()),height*data.Stride)
        finally:image.UnlockBits(data)
        info=_INFO()
        info.header=_HEADER(ctypes.sizeof(_HEADER),width,-height,1,32,0,0,0,0,0,0)
        screen=self.u.GetDC(None);dc=None;bitmap=None;old=None
        try:
            if not screen:raise ctypes.WinError(ctypes.get_last_error())
            dc=self.g.CreateCompatibleDC(screen)
            if not dc:raise ctypes.WinError(ctypes.get_last_error())
            pixels=ctypes.c_void_p();bitmap=self.g.CreateDIBSection(screen,ctypes.byref(info),0,ctypes.byref(pixels),None,0)
            if not bitmap or not pixels.value:raise ctypes.WinError(ctypes.get_last_error())
            old=self.g.SelectObject(dc,bitmap)
            if not old or int(old)==ctypes.c_void_p(-1).value:
                old=None;raise ctypes.WinError(ctypes.get_last_error())
            ctypes.memmove(pixels,raw,len(raw))
            point=W.POINT(self.target.Left-self.pad,self.target.Top-self.pad)
            size=_SIZE(width,height);source=W.POINT(0,0);blend=_BLEND(0,0,255,1)
            if not self.u.UpdateLayeredWindow(self.hwnd,screen,ctypes.byref(point),ctypes.byref(size),dc,ctypes.byref(source),0,ctypes.byref(blend),2):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if dc and old:self.g.SelectObject(dc,old)
            if bitmap:self.g.DeleteObject(bitmap)
            if dc:self.g.DeleteDC(dc)
            if screen:self.u.ReleaseDC(None,screen)

    def refresh(self,*_):
        if self.closed or self._busy:return
        if self.target.IsDisposed or not self.target.Visible:
            if self.hwnd:self.u.ShowWindow(self.hwnd,0)
            return
        self._busy=True
        try:
            width,height=self.target.Width,self.target.Height
            if width<=0 or height<=0:return
            surfaces=tuple(self.provider()) if self.provider else (((0,0,width,height),min(self.radius,width/2,height/2)),)
            c=self.fill if self.fill is not None else self.target.BackColor
            rgb=(c.R,c.G,c.B) if hasattr(c,'R') else tuple(c)
            key=(width,height,surfaces,rgb,self.scale)
            self._ensure()
            if key!=self._key:
                image,self.pad=render_edge((width,height),surfaces,rgb,self.scale)
                try:self._upload(image)
                finally:image.Dispose()
                self._key=key;self.render_count+=1
            self.move()
        except Exception as exc:
            self.error=type(exc).__name__;self.dispose()
        finally:self._busy=False

    def move(self,*_):
        if self.closed or not self.hwnd:return
        if self.target.IsDisposed or not self.target.Visible:
            self.u.ShowWindow(self.hwnd,0);return
        try:
            top=bool(self.target.TopMost)
            if top!=self._topmost:
                self.u.SetWindowPos(self.hwnd,W.HWND(-1 if top else -2),0,0,0,0,0x213)
                self._topmost=top
            # Insert AFTER target: beneath it, same z-order band, no activation.
            if not self.u.SetWindowPos(self.hwnd,W.HWND(int(self.target.Handle.ToInt64())),self.target.Left-self.pad,self.target.Top-self.pad,
                                     self.target.Width+2*self.pad,self.target.Height+2*self.pad,0x250):
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception as exc:
            self.error=type(exc).__name__;self.dispose()

    def dispose(self,*_):
        if self.closed:return
        self.closed=True
        target=self.target
        for name,fn in self._bindings:
            try:
                event=getattr(target,name);event-=fn
            except Exception:pass
        self._bindings=[]
        if self.visual is not None:
            try:self.visual.Dispose()
            except Exception:pass
        self.visual=None;self.hwnd=None;self._key=None
        self.provider=None;self.target=None
