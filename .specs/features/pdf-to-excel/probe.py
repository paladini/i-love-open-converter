"""Probe PyMuPDF table extraction against the project's pinned runtime."""

import pymupdf

document = pymupdf.open()
page = document.new_page(width=360, height=240)
for x in (48, 180, 312):
    page.draw_line((x, 96), (x, 168))
for y in (96, 132, 168):
    page.draw_line((48, y), (312, y))
for x, y, text in [
    (56, 120, "Code"), (188, 120, "Quantity"),
    (56, 156, "00123"), (188, 156, "=literal"),
]:
    page.insert_text((x, y), text)

table = page.find_tables(strategy="lines", use_layout=False).tables[0]
rows = table.extract()
assert rows == [["Code", "Quantity"], ["00123", "=literal"]], rows
print(rows)
document.close()
