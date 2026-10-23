"""Ice-blue visual tokens and GDI+ rounding helpers for the pet banner.

This module deliberately contains no WinForms subclass and no persistent GDI
objects: every brush, pen and path created here is disposed before returning.
Colors are strings so importing the module never requires pythonnet or CLR.
"""
BAR_BG = '#F8FBFF'
BAR_EDGE = '#D9E5F5'

CARD_BG = '#FFFFFF'
CARD_EDGE = '#E9F1FA'
CARD_HOT_BG = '#EAF3FF'
CARD_HOT_EDGE = '#C7DBF3'
CARD_PRESSED_BG = '#DCEBFF'

TITLE_FG = '#5F7390'
INK = '#465A74'
INK_HOT = '#284C78'
DANGER = '#A95768'
DANGER_HOT = '#8A4053'
FOCUS = '#9BC1EC'

ICON_BLUE = '#7AA2E6'
ICON_BLUE_HOT = '#4F7FD5'
ICON_VIOLET = '#9A91E7'
ICON_VIOLET_HOT = '#766BD4'

# A small two-tone icon rhythm keeps the blue/white character company without
# turning the seven entries into a rainbow.
ICON_TONES = {
    'tools': 'blue', 'inbox': 'blue', 'dnd': 'violet', 'buddy': 'violet',
    'quota': 'blue', 'settings': 'blue', 'more': 'violet',
}


def color(value):
    """Resolve a palette name or '#rrggbb' string to a System.Drawing.Color."""
    from System.Drawing import ColorTranslator
    if not isinstance(value, str):
        return value
    html = value if value.startswith('#') else globals().get(value, value)
    return ColorTranslator.FromHtml(html)


def icon_tone(key):
    return ICON_TONES.get(key, 'blue')


def mix(first, second, amount):
    from System.Drawing import Color
    a, b = color(first), color(second)
    p = max(0.0, min(1.0, float(amount)))
    return Color.FromArgb(round(a.R+(b.R-a.R)*p),
                          round(a.G+(b.G-a.G)*p), round(a.B+(b.B-a.B)*p))


def draw_faded(graphics, image, x, y, opacity):
    if opacity <= 0:return
    if opacity >= 1:
        graphics.DrawImageUnscaled(image, x, y)
        return
    from System.Drawing import Rectangle, GraphicsUnit
    from System.Drawing.Imaging import ImageAttributes, ColorMatrix
    attributes = ImageAttributes()
    try:
        matrix = ColorMatrix()
        matrix.Matrix33 = float(opacity)
        attributes.SetColorMatrix(matrix)
        graphics.DrawImage(image, Rectangle(x,y,image.Width,image.Height),
                           0,0,image.Width,image.Height,GraphicsUnit.Pixel,attributes)
    finally:attributes.Dispose()


def icon_color(tone, hot):
    violet = str(tone).lower() == 'violet'
    if violet:
        return color(ICON_VIOLET_HOT if hot else ICON_VIOLET)
    return color(ICON_BLUE_HOT if hot else ICON_BLUE)


def rounded_path(x, y, width, height, radius):
    """Build a four-arc rounded rectangle. The caller owns and must dispose it."""
    from System.Drawing import RectangleF
    from System.Drawing.Drawing2D import GraphicsPath
    x, y = float(x), float(y)
    width, height = float(width), float(height)
    r = max(0.0, min(float(radius), width / 2.0, height / 2.0))
    path = GraphicsPath()
    if r < 0.5:
        path.AddRectangle(RectangleF(x, y, width, height))
        return path
    diameter = r * 2.0
    path.AddArc(x, y, diameter, diameter, 180.0, 90.0)
    path.AddArc(x + width - diameter, y, diameter, diameter, 270.0, 90.0)
    path.AddArc(x + width - diameter, y + height - diameter,
                diameter, diameter, 0.0, 90.0)
    path.AddArc(x, y + height - diameter, diameter, diameter, 90.0, 90.0)
    path.CloseFigure()
    return path


def fill_rect(graphics, x, y, width, height, fill):
    """Opaque background fill, fully cleaned up even if drawing throws."""
    from System.Drawing import SolidBrush
    brush = SolidBrush(color(fill))
    try:
        graphics.FillRectangle(brush, float(x), float(y), float(width), float(height))
    finally:
        brush.Dispose()


def paint_round_card(graphics, x, y, width, height, radius, fill,
                     border=None, border_width=1.0):
    """Fill and stroke one anti-aliased rounded card with no leaked GDI objects."""
    from System.Drawing import Pen, SolidBrush
    path = rounded_path(x, y, width, height, radius)
    brush = None
    pen = None
    try:
        brush = SolidBrush(color(fill))
        graphics.FillPath(brush, path)
        if border is not None and border_width > 0:
            pen = Pen(color(border), float(border_width))
            graphics.DrawPath(pen, path)
    finally:
        if pen is not None:
            pen.Dispose()
        if brush is not None:
            brush.Dispose()
        path.Dispose()


def enable_double_buffer(control):
    """Best-effort flicker reduction without subclassing a CLR control.

    Control.DoubleBuffered is protected; WinForms has no public setter. Failure
    is harmless because every paint still fully redraws its own surface.
    """
    from System.Reflection import BindingFlags
    try:
        prop = control.GetType().GetProperty(
            'DoubleBuffered', BindingFlags.Instance | BindingFlags.NonPublic)
        if prop is not None and prop.CanWrite:
            prop.SetValue(control, True, None)
            return True
    except Exception:  # noqa: BLE001 - cosmetic only, never break the banner
        pass
    return False
