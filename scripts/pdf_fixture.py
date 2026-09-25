import io
from PIL import Image,ImageDraw


def sample_pdf():
    first=Image.new('RGB',(400,560),'white')
    ImageDraw.Draw(first).text((35,45),'PDF-Vorschau: Erste Seite',fill='black')
    second=Image.new('RGB',(400,560),'red')
    output=io.BytesIO()
    first.save(output,format='PDF',save_all=True,append_images=[second])
    return output.getvalue()
