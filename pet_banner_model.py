"""Pure layout and action catalog for the pet's native banner popup."""
import math

PRIMARY = (
    ('tools', '工具', '\ue8a5'), ('inbox', '提醒', '\ue7f4'),
    ('dnd', '勿扰', '\ue708'), ('buddy', '陪伴', '\ueb51'),
    ('quota', '额度', '\ue8d4'), ('settings', '设置', '\ue713'),
    ('more', '更多', '\ue712'),
)
MORE = (
    ('progress', '显示 / 隐藏进度'), ('refresh', '刷新进度信息'),
    ('pat', '摸摸头'), ('expression', '换个表情'), ('motion', '随机动作'),
    ('reminders', '任务提醒设置'), ('quiet', '游戏安静模式'),
    ('focus_agent', '切到 Agent 窗口'), ('agent', '切换 Agent'),
    ('reload', '重载形象'), ('repaint', '重画窗口'),
    ('hide', '隐藏到托盘'), ('quit', '退出桌宠'),
)

def banner_layout(scale, area, expanded=False):
    scale = max(1, min(4, float(scale)))
    px = lambda n: max(1, round(n * scale))
    available_w = max(200, area[2] - area[0] - 8)
    available_h = max(160, area[3] - area[1] - 8)
    pad, gap, tile = px(8), px(4), px(56)
    # Reserve space on the right for a native scrollbar on very small displays.
    reserve = px(12)
    columns = max(1, min(7, (available_w - 2 * pad - reserve + gap) // (tile + gap)))
    width = min(available_w, columns * (tile + gap) - gap + 2 * pad + reserve)
    top = px(24)
    primary = [(pad + (i % columns) * (tile + gap), top + (i // columns) * (tile + gap), tile, tile) for i in range(7)]
    main_bottom = top + math.ceil(7 / columns) * (tile + gap)
    more = []
    content_h = main_bottom + pad
    if expanded:
        extra_columns = min(3, columns)
        extra_w = (width - 2 * pad - reserve - (extra_columns - 1) * gap) // extra_columns
        extra_top = main_bottom + px(7)
        more = [(pad + (i % extra_columns) * (extra_w + gap), extra_top + (i // extra_columns) * px(33), extra_w, px(28)) for i in range(len(MORE))]
        content_h = extra_top + math.ceil(len(MORE) / extra_columns) * px(33) + pad
    return dict(width=width, height=min(available_h, content_h), content_height=content_h, primary=primary, more=more)

def clamp_popup(x, y, width, height, area):
    return (max(area[0] + 2, min(round(x), area[2] - width - 2)),
            max(area[1] + 2, min(round(y), area[3] - height - 2)))


def place_banner(pet, width, height, area, gap=12):
    """Prefer below the visible pet; use an unobstructed alternative if it will not fit."""
    left,top,right,bottom = pet
    center_x,center_y = (left+right)/2,(top+bottom)/2
    candidates = ((center_x-width/2,bottom+gap),
                  (center_x-width/2,top-height-gap),
                  (right+gap,center_y-height/2),
                  (left-width-gap,center_y-height/2))
    ranked = []
    for preference,(x,y) in enumerate(candidates):
        x,y = clamp_popup(x,y,width,height,area)
        overlap = max(0,min(x+width,right)-max(x,left))*max(0,min(y+height,bottom)-max(y,top))
        ranked.append((overlap,preference,x,y))
    _,_,x,y = min(ranked)
    return x,y
