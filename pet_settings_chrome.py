"""Opaque rounded settings host; narrow window-only WebView commands."""
import json, math


def decode_window_command(raw, origin, expected):
    if origin != expected or not isinstance(raw, str) or len(raw)>8192:return None
    try:data=json.loads(raw)
    except (ValueError,TypeError):return None
    if not isinstance(data,dict) or data.get('t')!='window':return None
    op=data.get('op')
    if op in ('close','drag'):return {'op':op}
    if op!='resize':return None
    phase=data.get('phase')
    if phase=='start':
        edge=data.get('edge')
        if not isinstance(edge,str) or edge not in ('n','ne','e','se','s','sw','w','nw'):return None
        return dict(op=op,phase=phase,edge=edge)
    if phase=='end':return dict(op=op,phase=phase)
    if phase!='move':return None
    dx,dy=data.get('dx'),data.get('dy')
    if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>20000 for v in (dx,dy)):return None
    return dict(op=op,phase=phase,dx=dx,dy=dy)


class SettingsChrome:
    def __init__(self,host,form,web,remember=None):
        from System.Windows.Forms import FormBorderStyle
        self.host=host;self.form=form;self.web=web;self.remember=remember
        self.page='http://127.0.0.1:%d/settings.html'%host.port
        self.closed=False;self.region=None;self.resizing=None;self.theme=None
        g=form.CreateGraphics()
        try:self.scale=max(1.0,g.DpiX/96.0)
        finally:g.Dispose()
        form.FormBorderStyle=getattr(FormBorderStyle,'None')
        self.set_theme(host.settings.get('settingsTheme'))
        form.SizeChanged+=self.round_region;form.FormClosed+=self.cleanup
        self.round_region()
        from pet_edge import EdgeHalo
        self.edge=EdgeHalo(form,scale=self.scale,radius=24)

    def set_theme(self,value):
        from System.Drawing import Color
        theme='ice' if value=='ice' else 'paper'
        if self.closed or theme==self.theme:return
        self.theme=theme
        self.form.BackColor=Color.FromArgb(*((243,247,252) if theme=='ice' else (251,249,243)))
        self.web.DefaultBackgroundColor=self.form.BackColor

    def round_region(self,*_):
        if self.closed:return
        from System.Drawing import Region
        from pet_banner_style import rounded_path
        path=rounded_path(0,0,self.form.Width,self.form.Height,round(24*self.scale))
        try:new=Region(path)
        finally:path.Dispose()
        old=self.region;self.region=new;self.form.Region=new
        if old is not None:old.Dispose()

    def handle(self,args):
        if self.closed:return False
        try:data=decode_window_command(args.WebMessageAsJson,str(args.Source),self.page)
        except Exception:return False
        if data is None:return False
        if data['op']=='close':self.form.Close()
        elif data['op']=='drag':
            from pet_metric_bubble import MetricBubble
            MetricBubble.drag(self)
        else:self.resize(data)
        return True

    def resize(self,data):
        phase=data['phase']
        if phase=='end':
            active=self.resizing is not None;self.resizing=None
            if active and self.remember:self.remember()
            return
        if phase=='start':
            from System.Windows.Forms import Screen
            b=self.form.Bounds;a=Screen.FromControl(self.form).WorkingArea
            self.resizing=dict(bounds=(b.Left,b.Top,b.Width,b.Height),edge=data['edge'],
                minimum=(self.form.MinimumSize.Width,self.form.MinimumSize.Height),area=(a.Left,a.Top,a.Right,a.Bottom))
            return
        state=self.resizing
        if state is None:return
        from pet_panel_actions import resize_bounds
        bounds=resize_bounds(state['bounds'],state['edge'],data['dx'],data['dy'],state['minimum'],state['area'])
        b=self.form.Bounds
        if bounds!=(b.Left,b.Top,b.Width,b.Height):self.form.SetBounds(*bounds)

    def cleanup(self,*_):
        if self.closed:return
        self.closed=True;self.resizing=None
        self.form.SizeChanged-=self.round_region;self.form.FormClosed-=self.cleanup
        if self.region is not None:self.region.Dispose();self.region=None
        if getattr(self.host,'settings_chrome',None) is self:self.host.settings_chrome=None
