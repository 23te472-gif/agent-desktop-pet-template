"""Pure layout and action catalog for the pet's native banner popup."""
import math

PRIMARY = (
    ('tools', '工具', '\ue8a5'), ('interaction', '互动', '\ueb51'),
    ('console', '控制台', '\ue7f4'),
    ('quota', '额度', '\ue8d4'), ('settings', '设置', '\ue713'),
    ('more', '更多', '\ue712'),
)
INTERACTIONS = (('pat', '摸摸头'), ('expression', '换个表情'), ('motion', '随机动作'))
MORE = (
    ('progress', '显示 / 隐藏进度'), ('refresh', '刷新进度信息'),
    ('focus_agent', '切到 Agent 窗口'), ('agent', '切换 Agent'),
    ('reload', '重载形象'), ('repaint', '重画窗口'),
    ('hide', '隐藏到托盘'), ('quit', '退出桌宠'),
)


def banner_layout(scale, area, expanded=False, interaction=False):
    """Lay out a grouped 68px bar, or a wrapped compact bar when space is tight.

    The wide presets are deliberately grouped as 1 + 2 + 3. The existing
    PRIMARY/MORE tuples stay intact so every native action is preserved.
    """
    entries = INTERACTIONS if interaction else MORE
    expanded = expanded or interaction
    scale = max(1, min(4, float(scale)))
    px = lambda n: max(1, round(n * scale))
    available_w = max(200, area[2] - area[0] - 8)
    available_h = max(160, area[3] - area[1] - 8)

    pad = px(8)
    group_gap = px(8)
    inner_gap = px(3)
    utility_gap = px(2)
    button_h = px(52)
    bar_h = px(66)
    top = max(0, (bar_h - button_h) // 2)

    tools_w = px(86)
    mode_w = px(58)
    utility_w = px(44)
    modes_w = 2 * mode_w + inner_gap
    utilities_w = 3 * utility_w + 2 * utility_gap
    wide_width = 2 * pad + tools_w + modes_w + utilities_w + 2 * group_gap

    if available_w >= wide_width:
        width = wide_width
        primary = []
        separators = []
        x = pad
        primary.append((x, top, tools_w, button_h))
        x += tools_w + group_gap
        separators.append(x - group_gap // 2)
        for _ in range(2):
            primary.append((x, top, mode_w, button_h))
            x += mode_w + inner_gap
        x -= inner_gap
        x += group_gap
        separators.append(x - group_gap // 2)
        for _ in range(3):
            primary.append((x, top, utility_w, button_h))
            x += utility_w + utility_gap
        content_h = bar_h
        more = _more_layout(width, bar_h, px, expanded, columns=3, reserve=0, entries=entries)
        if more:
            content_h = more[0]
        return dict(width=width, height=min(available_h, content_h),
                    content_height=content_h, primary=primary, more=more[1] if more else [],
                    separators=separators)

    # Narrow work areas retain wrapping and a native scrollbar path.
    reserve = px(12)
    tile = px(52)
    gap = px(4)
    columns = max(1, min(len(PRIMARY), (available_w - 2 * pad - reserve + gap) // (tile + gap)))
    width = min(available_w, columns * (tile + gap) - gap + 2 * pad + reserve)
    primary = [(pad + (i % columns) * (tile + gap),
                top + (i // columns) * (tile + gap), tile, tile)
               for i in range(len(PRIMARY))]
    rows = int(math.ceil(len(PRIMARY) / float(columns)))
    main_bottom = top + rows * tile + (rows - 1) * gap
    content_h = main_bottom + top
    more = _more_layout(width, main_bottom, px, expanded,
                        columns=min(3, columns), reserve=reserve, extra_top=px(7), entries=entries)
    if more:
        content_h = more[0]
    return dict(width=width, height=min(available_h, content_h),
                content_height=content_h, primary=primary, more=more[1] if more else [],
                separators=[])


def _more_layout(width, main_bottom, px, expanded, columns, reserve=0, extra_top=0, entries=MORE):
    if not expanded:
        return None
    gap = px(4)
    column_count = max(1, min(3, int(columns)))
    extra_w = max(1, (width - 2 * px(8) - reserve - (column_count - 1) * gap) // column_count)
    top = main_bottom + (extra_top if extra_top else px(7))
    more = [(px(8) + (i % column_count) * (extra_w + gap),
             top + (i // column_count) * px(33), extra_w, px(28))
            for i in range(len(entries))]
    content_h = top + int(math.ceil(len(entries) / float(column_count))) * px(33) + px(8)
    return content_h, more


def clamp_popup(x, y, width, height, area):
    return (max(area[0] + 2, min(round(x), area[2] - width - 2)),
            max(area[1] + 2, min(round(y), area[3] - height - 2)))


def place_banner(pet, width, height, area, gap=12):
    """Prefer below the visible pet; use an unobstructed alternative if it will not fit."""
    left, top, right, bottom = pet
    center_x, center_y = (left + right) / 2, (top + bottom) / 2
    candidates = ((center_x - width / 2, bottom + gap),
                  (center_x - width / 2, top - height - gap),
                  (right + gap, center_y - height / 2),
                  (left - width - gap, center_y - height / 2))
    ranked = []
    for preference, (x, y) in enumerate(candidates):
        x, y = clamp_popup(x, y, width, height, area)
        overlap = max(0, min(x + width, right) - max(x, left)) * max(0, min(y + height, bottom) - max(y, top))
        ranked.append((overlap, preference, x, y))
    _, _, x, y = min(ranked)
    return x, y


def more_popup_layout(scale, area):
    """Compact grouped command card; coordinates are relative to its own panel."""
    scale=max(1,min(4,float(scale)))
    px=lambda n:max(1,round(n*scale))
    width=min(px(380),max(180,area[2]-area[0]-8))
    pad,heading,gap=px(9),px(36),px(3)
    row_h=px(36)
    rows=(('进度',MORE[:2]),('窗口',MORE[2:4]),('系统',MORE[4:7]))
    entries=[];headings=[];dividers=[]
    y=pad
    for title,actions in rows:
        headings.append((title,(pad,y,heading,row_h)))
        start=pad+heading+gap
        available=width-pad-start
        count=len(actions)
        for i,(key,_) in enumerate(actions):
            x=start+round(i*available/count)
            right=start+round((i+1)*available/count)-gap
            entries.append((key,(x,y,max(1,right-x),row_h)))
        y+=row_h+px(6)
        dividers.append(y-px(3))
    entries.append(('quit',(pad,y,width-2*pad,px(32))))
    return dict(width=width,height=y+px(32)+pad,entries=entries,
                headings=headings,dividers=dividers)


def place_more(pet, bar, size, area, gap=10):
    """Prefer beside the bar and character; fallback above/below on small screens."""
    width,height=size
    lo,hi=area[0]+2,area[2]-2
    right=max(bar[2],pet[2])+gap
    left=min(bar[0],pet[0])-width-gap
    for x in (right,left):
        if x>=lo and x+width<=hi:
            return clamp_popup(x,bar[3]-height,width,height,area)
    candidates=((bar[2]-width,bar[1]-height-gap),
                (bar[2]-width,bar[3]+gap))
    rank=[]
    def overlap(x,y,rect):
        return max(0,min(x+width,rect[2])-max(x,rect[0]))*max(0,min(y+height,rect[3])-max(y,rect[1]))
    for i,(x,y) in enumerate(candidates):
        x,y=clamp_popup(x,y,width,height,area)
        rank.append((overlap(x,y,bar),overlap(x,y,pet),i,x,y))
    *_,x,y=min(rank)
    return x,y


def more_popup_bounds(pet, bar, size, area, gap=10):
    width,height=size
    side_fits=(max(bar[2],pet[2])+gap+width<=area[2]-2 or
               min(bar[0],pet[0])-width-gap>=area[0]+2)
    space=area[3]-area[1]-8 if side_fits else max(bar[1]-area[1]-gap-2,area[3]-bar[3]-gap-2)
    if space<24:return None
    height=min(height,int(space))
    x,y=place_more(pet,bar,(width,height),area,gap)
    return x,y,width,height


def _overlap_xywh(rect, obstacle):
    x,y,w,h=rect
    return x<obstacle[2] and x+w>obstacle[0] and y<obstacle[3] and y+h>obstacle[1]


def orbit_layout(pet, area, scale, bar=None):
    """Three separate circular targets; no giant invisible radial hit surface."""
    scale=max(1,min(4,float(scale)))
    px=lambda n:max(1,round(n*scale))
    diameter=min(px(46),max(20,(area[3]-area[1]-12)//3-4))
    radius=diameter/2
    left_room,right_room=pet[0]-area[0],area[2]-pet[2]
    side='right' if right_room>=left_room else 'left'
    center=(pet[1]+pet[3])/2
    spacing=max(diameter+px(8),(pet[3]-pet[1])*.26)
    spacing=min(spacing,max(diameter,(area[3]-area[1]-diameter-8)/2))
    first=max(area[1]+4,min(center-spacing-radius,area[3]-diameter-2*spacing-4))
    label_width=min(px(100),max(100,area[2]-area[0]-diameter-16))
    label_h=px(30)
    for candidate in (side,'left' if side=='right' else 'right'):
        room=right_room if candidate=='right' else left_room
        if bar is not None and room<diameter+px(8):continue
        entries=[];labels={}
        for i,(key,_) in enumerate(INTERACTIONS):
            bulge=px(15) if i==1 else 0
            x=pet[2]+px(8)+bulge if candidate=='right' else pet[0]-diameter-px(8)-bulge
            x=max(area[0]+4,min(round(x),area[2]-diameter-4))
            y=round(first+i*spacing)
            entries.append((key,(x,y,diameter,diameter)))
            outward=x+diameter+px(5) if candidate=='right' else x-label_width-px(5)
            inward=x-label_width-px(5) if candidate=='right' else x+diameter+px(5)
            for lx in (outward,inward):
                rect=(round(lx),round(y+(diameter-label_h)/2),label_width,label_h)
                if area[0]+2<=lx and lx+label_width<=area[2]-2 and (bar is None or not _overlap_xywh(rect,bar)):
                    labels[key]=rect;break
        if bar is None or not any(_overlap_xywh(rect,bar) for key,rect in entries):
            return dict(side=candidate,entries=entries,labels=labels)
    return dict(side=side,entries=[],labels={},unavailable=True)


def surface_bounds(surfaces):
    """Bounding box only; do not use this rectangle as the actual hit region."""
    rects=[r for r,_ in surfaces]
    return (min(r[0] for r in rects),min(r[1] for r in rects),
            max(r[0]+r[2] for r in rects),max(r[1]+r[3] for r in rects))


def contains_surface(point, surfaces):
    if not point:return False
    x,y=point
    for (left,top,width,height),radius in surfaces:
        if not (left<=x<left+width and top<=y<top+height):continue
        r=max(0,min(radius,width/2,height/2))
        cx=max(left+r,min(x,left+width-r))
        cy=max(top+r,min(y,top+height-r))
        if (x-cx)**2+(y-cy)**2<=r*r:return True
    return False
