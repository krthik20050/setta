"""Photo-first people tile rendering; images remain local."""
import io
from PIL import Image, ImageOps, ImageDraw, ImageFont


def face_avatar(data, size=88):
    """Render a compact, circular face crop for the People gallery."""
    with Image.open(io.BytesIO(data)) as source:
        image = ImageOps.fit(source.convert('RGB'), (size, size), method=Image.Resampling.LANCZOS,
                             centering=(.5, .38)).convert('RGBA')
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    image.putalpha(mask)
    return image


def portrait_tile(data, name, size=(180, 232)):
    with Image.open(io.BytesIO(data)) as source:
        image = ImageOps.fit(source.convert('RGB'), size, method=Image.Resampling.LANCZOS, centering=(.5, .35)).convert('RGBA')
    width, height = size
    shade = Image.new('RGBA', size)
    draw = ImageDraw.Draw(shade)
    for y in range(height // 2, height):
        alpha = int(195 * max(0, (y-height/2)/(height/2)) ** 1.3)
        draw.line((0,y,width,y), fill=(0,0,0,alpha))
    image = Image.alpha_composite(image, shade)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 19)
    except OSError:
        font = ImageFont.load_default(size=19)
    words = str(name).replace('_', ' ').split()
    lines, line = [], ''
    for word in words:
        trial = (line + ' ' + word).strip()
        if line and draw.textlength(trial, font=font) > width-24:
            lines.append(line); line=word
        else:
            line=trial
    if line:
        lines.append(line)
    lines=lines[:2] or [str(name)]
    for index, text in enumerate(lines):
        while draw.textlength(text, font=font) > width-24 and len(text)>1:
            text=text[:-2]+'…'
        draw.text((12,height-14-24*(len(lines)-index)),text,font=font,fill='white')
    mask=Image.new('L',size,0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),radius=20,fill=255)
    image.putalpha(mask)
    return image
