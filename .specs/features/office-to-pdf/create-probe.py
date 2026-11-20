from pathlib import Path

from docx import Document
from openpyxl import Workbook
from pptx import Presentation

root = Path(__file__).parent / "probe-files"
root.mkdir(exist_ok=True)
document = Document()
document.add_paragraph("Word probe content")
document.save(root / "word.docx")
workbook = Workbook()
workbook.active["A1"] = "Excel probe content"
workbook.save(root / "excel.xlsx")
presentation = Presentation()
slide = presentation.slides.add_slide(presentation.slide_layouts[1])
slide.shapes.title.text = "PowerPoint probe content"
presentation.save(root / "powerpoint.pptx")
