"""Cloud outline and text pagination shared by the Tk bubble and previews."""
import math


def bubble_layout(text, measure, line_height=17, max_height=250, max_width=440):
    """Grow to fit text, then paginate at a bounded readable size."""
    pixels = measure(str(text).replace('\n',' '))
    width = min(max_width, 280 if pixels<550 else 360 if pixels<1500 else 440)
    width = max(220,width)
    max_lines = max(1,int((max_height-44)/line_height))
    pages = wrap_pages(text,measure,width=width-75,max_lines=max_lines)
    lines = max(len(page.split('\n')) for page in pages)
    height = min(max_height,max(78,lines*line_height+44))
    return width,height,pages


def cloud_points(width: float, height: float, x: float = 8, y: float = 8) -> list[float]:
    # Irregular rounded lobes, deliberately unlike a rectangular chat box.
    anchors = [(.11,.80),(.02,.79),(.0,.65),(.02,.50),(.12,.43),(.11,.29),
        (.18,.13),(.29,.12),(.34,.20),(.38,.05),(.50,.0),(.61,.13),
        (.67,.03),(.80,.0),(.93,.15),(.97,.32),(.93,.47),(.98,.57),
        (1.,.74),(.94,.87),(.85,.86),(.83,.98),(.74,1.),(.65,.89),
        (.59,.99),(.47,1.),(.38,.95),(.32,1.),(.22,.98),(.14,.90)]
    return [value for px, py in anchors for value in (x+px*width,y+py*height)]


def wrap_pages(text: str, measure, width: int = 205, max_lines: int = 3) -> list[str]:
    lines=[]
    for paragraph in str(text).split('\n'):
        line=''
        for word in paragraph.split():
            proposed=(line+' '+word).strip()
            if line and measure(proposed)>width:
                lines.append(line);line=word
            else:
                line=proposed
        if line: lines.append(line)
    lines=lines or ['']
    return ['\n'.join(lines[i:i+max_lines]) for i in range(0,len(lines),max_lines)]


def float_offset(seconds: float) -> float:
    return 1.4*math.sin(seconds*2.0)


def draw_cloud(canvas, width: int, text: str, font, height=78) -> None:
    canvas.create_polygon(*cloud_points(width-16,height), smooth=True, splinesteps=16,
        fill='#fffdf5',outline='#394b3d',width=2,tags='bubble')
    canvas.create_oval(width*.46-5,height+13,width*.46+5,height+23,
        fill='#fffdf5',outline='#394b3d',width=1.7,tags='bubble')
    canvas.create_oval(width*.50-2.5,height+28,width*.50+2.5,height+33,
        fill='#fffdf5',outline='#394b3d',width=1.4,tags='bubble')
    canvas.create_text(width/2,height/2+8,text=text,width=width-75,justify='center',
        fill='#253c2e',font=font,tags='bubble')
