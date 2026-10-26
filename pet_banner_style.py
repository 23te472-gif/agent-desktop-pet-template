"""Deep ink-green visual tokens and GDI+ rounding helpers for the pet banner.

This module deliberately contains no WinForms subclass and no persistent GDI
objects: every brush, pen and path created here is disposed before returning.
Colors are strings so importing the module never requires pythonnet or CLR.
"""
BAR_BG = '#16241D'
BAR_TOP_BG = '#1E2E25'
BAR_BOTTOM_BG = '#0F1914'
BAR_EDGE = '#35473C'
BAR_TOP_LIGHT = '#3D5044'
BAR_BOTTOM_SHADE = '#09110D'
TOOL_BG = '#1E3027'
DIVIDER = '#35483C'

CARD_BG = '#18261F'
CARD_TOP_BG = '#1B2B23'
CARD_BOTTOM_BG = '#142019'
CARD_TOP_LIGHT = '#405547'
CARD_EDGE = '#2D4034'
CARD_HOT_BG = '#273B2F'
CARD_HOT_TOP_BG = '#273C30'
CARD_HOT_BOTTOM_BG = '#1C2C23'
CARD_HOT_TOP_LIGHT = '#587260'
CARD_HOT_EDGE = '#435E4C'
CARD_PRESSED_BG = '#131F18'
CARD_PRESSED_TOP_BG = '#142019'
CARD_PRESSED_BOTTOM_BG = '#0E1813'
CARD_PRESSED_TOP_LIGHT = '#2B3F34'
CARD_SHADOW = '#08100C'
TOOL_TOP_BG = '#21352A'
TOOL_BOTTOM_BG = '#18261E'

TITLE_FG = '#AFC4B7'
INK = '#E7F0EB'
INK_HOT = '#FFFFFF'
DANGER = '#DCA0A6'
DANGER_HOT = '#FFD4D8'
FOCUS = '#8ED9B4'

ICON_MINT = '#9BD8BA'
ICON_MINT_HOT = '#D9F6E6'
ICON_BLUE = '#9CC5D2'
ICON_BLUE_HOT = '#D7EEF4'
# Kept as aliases for callers that still use the old violet tone names.
ICON_VIOLET = ICON_MINT
ICON_VIOLET_HOT = ICON_MINT_HOT

# Two quiet tones separate the primary/mode group from utility actions without
# turning seven entries into a rainbow.
ICON_TONES = {
    'tools': 'mint', 'inbox': 'mint', 'dnd': 'mint', 'buddy': 'mint',
    'quota': 'blue', 'settings': 'blue', 'more': 'blue',
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
    mint = str(tone).lower() in ('mint', 'violet')
    if mint:
        return color(ICON_MINT_HOT if hot else ICON_MINT)
    return color(ICON_BLUE_HOT if hot else ICON_BLUE)


def draw_dot(graphics, x, y, radius, fill):
    """Draw one small status dot with no owned GDI state left behind."""
    from System.Drawing import SolidBrush
    brush = SolidBrush(color(fill))
    try:
        r = max(0.5, float(radius))
        graphics.FillEllipse(brush, float(x) - r, float(y) - r, r * 2.0, r * 2.0)
    finally:
        brush.Dispose()


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


def paint_vertical_gradient(graphics, x, y, width, height, top, bottom):
    """Opaque vertical wash for the bar; disposed locally on every paint."""
    from System.Drawing import RectangleF
    from System.Drawing.Drawing2D import LinearGradientBrush, LinearGradientMode
    brush = None
    try:
        brush = LinearGradientBrush(RectangleF(float(x), float(y), float(width), float(height)),
                                    color(top), color(bottom), LinearGradientMode.Vertical)
        graphics.FillRectangle(brush, float(x), float(y), float(width), float(height))
    finally:
        if brush is not None:
            brush.Dispose()


def paint_depth_card(graphics, x, y, width, height, radius, top, bottom,
                     border=None, border_width=1.0, top_light=None,
                     highlight_width=1.0, shadow=None, shadow_offset=1.0):
    """Paint a soft raised surface without leaving the caller's control bounds.

    The shadow is a single dark rounded layer just below the card. Callers
    reserve that one or two pixel strip inside the native button client area.
    """
    from System.Drawing import Pen, RectangleF, SolidBrush
    from System.Drawing.Drawing2D import LinearGradientBrush, LinearGradientMode
    resources = []
    try:
        if shadow is not None:
            shadow_path = rounded_path(x, y + float(shadow_offset), width, height, radius)
            resources.append(shadow_path)
            shadow_brush = SolidBrush(color(shadow))
            resources.append(shadow_brush)
            graphics.FillPath(shadow_brush, shadow_path)

        path = rounded_path(x, y, width, height, radius)
        resources.append(path)
        gradient = LinearGradientBrush(RectangleF(float(x), float(y), float(width), float(height)),
                                       color(top), color(bottom), LinearGradientMode.Vertical)
        resources.append(gradient)
        graphics.FillPath(gradient, path)

        if border is not None and border_width > 0:
            border_pen = Pen(color(border), float(border_width))
            resources.append(border_pen)
            graphics.DrawPath(border_pen, path)

        if top_light is not None:
            inset = max(3.0, float(radius) * 0.55)
            start = float(x) + inset
            end = float(x + width) - inset
            if end > start:
                light_pen = Pen(color(top_light), float(max(1.0, highlight_width)))
                resources.append(light_pen)
                graphics.DrawLine(light_pen, start, float(y) + 1.0, end, float(y) + 1.0)
    finally:
        for resource in reversed(resources):
            resource.Dispose()


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


PALETTE_KEYS = (
    'BAR_BG', 'BAR_TOP_BG', 'BAR_BOTTOM_BG', 'BAR_EDGE', 'BAR_TOP_LIGHT',
    'BAR_BOTTOM_SHADE', 'TOOL_BG', 'DIVIDER',
    'CARD_BG', 'CARD_TOP_BG', 'CARD_BOTTOM_BG', 'CARD_TOP_LIGHT', 'CARD_EDGE',
    'CARD_HOT_BG', 'CARD_HOT_TOP_BG', 'CARD_HOT_BOTTOM_BG', 'CARD_HOT_TOP_LIGHT',
    'CARD_HOT_EDGE', 'CARD_PRESSED_BG', 'CARD_PRESSED_TOP_BG',
    'CARD_PRESSED_BOTTOM_BG', 'CARD_PRESSED_TOP_LIGHT', 'CARD_SHADOW',
    'TOOL_TOP_BG', 'TOOL_BOTTOM_BG',
    'TITLE_FG', 'INK', 'INK_HOT', 'DANGER', 'DANGER_HOT', 'FOCUS',
    'ICON_MINT', 'ICON_MINT_HOT', 'ICON_BLUE', 'ICON_BLUE_HOT',
)


def _palette_color(palette, value):
    """Resolve a palette attribute name or '#rrggbb' for one banner instance."""
    from System.Drawing import ColorTranslator
    if not isinstance(value, str):
        return value
    html = value if value.startswith('#') else getattr(palette, value, value)
    return ColorTranslator.FromHtml(html)


class Palette:
    """A banner-local colour set plus wrappers around the shared GDI helpers."""

    def __init__(self, values, name='paper', tint_icons=False):
        self.__dict__.update(values)
        self.name = name
        self.TINT_ICONS = bool(tint_icons)

    def color(self, value):
        return _palette_color(self, value)

    def mix(self, first, second, amount):
        return mix(self.color(first), self.color(second), amount)

    def icon_tone(self, key):
        return icon_tone(key)

    def icon_color(self, tone, hot):
        mint = str(tone).lower() in ('mint', 'violet')
        if mint:
            return self.color(self.ICON_MINT_HOT if hot else self.ICON_MINT)
        return self.color(self.ICON_BLUE_HOT if hot else self.ICON_BLUE)

    def icon_tint(self, tone):
        mint = str(tone).lower() in ('mint', 'violet')
        return self.color(self.ICON_MINT if mint else self.ICON_BLUE)

    def fill_rect(self, graphics, x, y, width, height, fill):
        return fill_rect(graphics, x, y, width, height, self.color(fill))

    def draw_dot(self, graphics, x, y, radius, fill):
        return draw_dot(graphics, x, y, radius, self.color(fill))

    def rounded_path(self, *args, **kwargs):
        return rounded_path(*args, **kwargs)

    def paint_round_card(self, graphics, x, y, width, height, radius, fill,
                         border=None, border_width=1.0):
        return paint_round_card(
            graphics, x, y, width, height, radius, self.color(fill),
            self.color(border) if border is not None else None, border_width)

    def paint_vertical_gradient(self, graphics, x, y, width, height, top, bottom):
        return paint_vertical_gradient(
            graphics, x, y, width, height, self.color(top), self.color(bottom))

    def paint_depth_card(self, graphics, x, y, width, height, radius, top, bottom,
                         border=None, border_width=1.0, top_light=None,
                         highlight_width=1.0, shadow=None, shadow_offset=1.0):
        return paint_depth_card(
            graphics, x, y, width, height, radius,
            self.color(top), self.color(bottom),
            self.color(border) if border is not None else None,
            border_width,
            self.color(top_light) if top_light is not None else None,
            highlight_width,
            self.color(shadow) if shadow is not None else None,
            shadow_offset)

    def enable_double_buffer(self, control):
        return enable_double_buffer(control)


PAPER_VALUES = {name: globals()[name] for name in PALETTE_KEYS}

# Cold white / cool-grey bar with blue icons and high-contrast navy text.
ICE_VALUES = {
    'BAR_BG': '#F7F9FC',
    'BAR_TOP_BG': '#FAFCFF',
    'BAR_BOTTOM_BG': '#F3F6FA',
    'BAR_EDGE': '#D6E0EC',
    'BAR_TOP_LIGHT': '#FFFFFF',
    'BAR_BOTTOM_SHADE': '#E1E8F1',
    'TOOL_BG': '#F1F5FA',
    'DIVIDER': '#E3E9F1',
    'CARD_BG': '#FAFCFF',
    'CARD_TOP_BG': '#FCFDFF',
    'CARD_BOTTOM_BG': '#F4F7FB',
    'CARD_TOP_LIGHT': '#FFFFFF',
    'CARD_EDGE': '#DCE5EF',
    'CARD_HOT_BG': '#EDF3FB',
    'CARD_HOT_TOP_BG': '#F3F7FD',
    'CARD_HOT_BOTTOM_BG': '#E7EFF9',
    'CARD_HOT_TOP_LIGHT': '#FFFFFF',
    'CARD_HOT_EDGE': '#A5BFDD',
    'CARD_PRESSED_BG': '#E5EDF8',
    'CARD_PRESSED_TOP_BG': '#EAF1FA',
    'CARD_PRESSED_BOTTOM_BG': '#DFE9F5',
    'CARD_PRESSED_TOP_LIGHT': '#FFFFFF',
    'CARD_SHADOW': '#D6E0ED',
    'TOOL_TOP_BG': '#F7FAFE',
    'TOOL_BOTTOM_BG': '#EDF3FA',
    'TITLE_FG': '#607288',
    'INK': '#293B50',
    'INK_HOT': '#19334F',
    'DANGER': '#A34B58',
    'DANGER_HOT': '#8B3543',
    'FOCUS': '#3A74C5',
    'ICON_MINT': '#426FA7',
    'ICON_MINT_HOT': '#315F98',
    'ICON_BLUE': '#4B75A8',
    'ICON_BLUE_HOT': '#315F98',
}

PAPER = Palette(PAPER_VALUES, 'paper', False)
ICE = Palette(ICE_VALUES, 'ice', True)


def for_theme(theme):
    """Return a fresh per-banner palette; never mutate module globals."""
    if str(theme).lower() == 'ice':
        return Palette(ICE_VALUES, 'ice', True)
    return Palette(PAPER_VALUES, 'paper', False)

