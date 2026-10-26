"""Prefer an installed rounded Chinese font, with portable system fallbacks."""
_family = None

def rounded_font(size=10.5, bold=True):
    global _family
    from System.Drawing import Font,FontFamily,FontStyle
    from System.Drawing.Text import InstalledFontCollection
    if _family is None:
        fonts=InstalledFontCollection()
        try:
            available={str(f.Name).casefold():str(f.Name) for f in fonts.Families}
            _family=next((available[name.casefold()] for name in
                ('YouYuan','幼圆','Yuanti SC','华文圆体','Microsoft YaHei UI','Segoe UI')
                if name.casefold() in available),'Microsoft Sans Serif')
        finally:fonts.Dispose()
    family=FontFamily(_family)
    try:
        style=FontStyle.Bold if bold and family.IsStyleAvailable(FontStyle.Bold) else FontStyle.Regular
        return Font(family,float(size),style)
    finally:family.Dispose()
