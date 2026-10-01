"""QA documental: texto e folhas de contato das páginas renderizadas."""
from pathlib import Path
from PIL import Image, ImageDraw
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1]
reader = PdfReader(root/"output/pdf/guia_jacare_analytics.pdf")
print("Páginas:", len(reader.pages))
for i, page in enumerate(reader.pages, 1):
    text = page.extract_text()
    assert len(text) > 300, f"Página vazia: {i}"
    assert "Sem dados confidenciais" in text
    print(i, len(text), "caracteres")
paths = sorted((root/"tmp/pdfs").glob("guia-*.png"))
assert len(paths) == len(reader.pages)
for start in range(0, len(paths), 4):
    sheet = Image.new("RGB", (1200, 1740), "#DDE5E1")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths[start:start+4]):
        im = Image.open(path).convert("RGB")
        im.thumbnail((580, 820))
        x, y = (index%2)*600+10, (index//2)*870+30
        sheet.paste(im, (x,y))
        draw.text((x,y-20), path.stem, fill="black")
    sheet.save(root/f"tmp/pdfs/review-{start//4+1}.png")
