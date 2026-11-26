"""Builds the presentation (PowerPoint file). Run from the project folder:

    uv run --no-project --with python-pptx python reports/presentation/build_deck.py

Then make the PDF from the PowerPoint file, for example with LibreOffice:

    soffice --headless --convert-to pdf --outdir reports/presentation reports/presentation/ev_charging_gap.pptx

The numbers on the slides come from the README and the notebooks of this project.
"""

from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION, XL_TICK_MARK
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIGURES = HERE / "figures"
OUTPUT = HERE / "ev_charging_gap.pptx"

# Palette: dark blue-green as the main colour, the chart blue of the notebooks, and red only for "below expected".
NAVY, BLUE, LIGHT_BLUE, GREY = "12313F", "2A6F97", "8FB8D4", "B0B0B0"
RED, INK, MUTED, PANEL, WHITE = "B2182B", "1F2933", "5B6770", "EEF3F6", "FFFFFF"
HEAD_FONT, BODY_FONT, MONO_FONT = "Cambria", "Calibri", "Courier New"
LEFT, CENTER, RIGHT = PP_ALIGN.LEFT, PP_ALIGN.CENTER, PP_ALIGN.RIGHT

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def set_bullet(paragraph, indent: float = 0.24) -> None:
    """A real bullet (not a typed character), with a hanging indent."""
    properties = paragraph._p.get_or_add_pPr()
    properties.set("marL", str(int(Inches(indent))))
    properties.set("indent", str(-int(Inches(indent))))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum"):
        for old in properties.findall(qn(tag)):
            properties.remove(old)
    bullet = etree.SubElement(properties, qn("a:buChar"))
    bullet.set("char", "•")


def add_text(slide, x, y, w, h, items, size=16, color=INK, font=BODY_FONT, bold=False, align=LEFT,
             anchor=MSO_ANCHOR.TOP, margin=0.0, space_after=6, name=None):
    """A text box. `items` is a list of strings or dicts (text, size, bold, color, bullet, font, align, space_after).
    The text of an item can be a list of (text, options) runs."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    frame = box.text_frame
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = anchor
    for index, item in enumerate(items):
        item = {"text": item} if isinstance(item, str) else item
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.alignment = item.get("align", align)
        paragraph.space_after = Pt(item.get("space_after", space_after))
        runs = item["text"] if isinstance(item["text"], list) else [(item["text"], {})]
        for text, options in runs:
            run = paragraph.add_run()
            run.text = text
            run.font.name = options.get("font", item.get("font", font))
            run.font.size = Pt(options.get("size", item.get("size", size)))
            run.font.bold = options.get("bold", item.get("bold", bold))
            run.font.color.rgb = rgb(options.get("color", item.get("color", color)))
        if item.get("bullet"):
            set_bullet(paragraph)
    return box


def add_card(slide, x, y, w, h, fill=PANEL, radius=0.05, name=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.adjustments[0] = radius
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.line.fill.background()
    shape.shadow.inherit = False
    if name:
        shape.name = name
    return shape


def add_arrow(slide, x, y, w=0.2, h=0.3, color=MUTED):
    shape = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(color)
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def add_image(slide, path, x, y, w, h, name=None):
    """Place a picture inside the box, as large as possible and centred, without changing its proportions."""
    from PIL import Image

    with Image.open(path) as image:
        ratio = image.width / image.height
    width, height = (w, w / ratio) if w / h < ratio else (h * ratio, h)
    picture = slide.shapes.add_picture(str(path), Inches(x + (w - width) / 2), Inches(y + (h - height) / 2), Inches(width), Inches(height))
    if name:
        picture.name = name
    return picture


def add_table(slide, x, y, widths, rows, row_height=0.6, size=14, header_fill=NAVY, first_col_bold=False, align_right_from=None):
    """A table. rows[0] is the header. Columns from `align_right_from` on are right-aligned."""
    table_shape = slide.shapes.add_table(len(rows), len(widths), Inches(x), Inches(y), Inches(sum(widths)), Inches(row_height * len(rows)))
    table = table_shape.table
    table.first_row, table.horz_banding = True, False
    for column, width in enumerate(widths):
        table.columns[column].width = Inches(width)
    for r, row in enumerate(rows):
        table.rows[r].height = Inches(row_height)
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(header_fill if r == 0 else (WHITE if r % 2 else PANEL))
            cell.margin_left = cell.margin_right = Inches(0.1)
            cell.margin_top = cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            frame = cell.text_frame
            frame.word_wrap = True
            paragraph = frame.paragraphs[0]
            paragraph.alignment = RIGHT if (align_right_from is not None and c >= align_right_from) else LEFT
            run = paragraph.add_run()
            run.text = value
            run.font.name, run.font.size = BODY_FONT, Pt(size)
            run.font.bold = r == 0 or (first_col_bold and c == 0)
            run.font.color.rgb = rgb(WHITE if r == 0 else INK)
    return table_shape


def new_slide(dark=False):
    slide = prs.slides.add_slide(BLANK)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(NAVY if dark else WHITE)
    return slide


def add_title(slide, text, color=INK):
    add_text(slide, 0.6, 0.4, 12.1, 1.1, [text], size=32, bold=True, font=HEAD_FONT, color=color, anchor=MSO_ANCHOR.TOP, name="Title")


def add_footer(slide, number, source=None):
    if source:
        add_text(slide, 0.6, 7.02, 11.0, 0.3, [source], size=11, color=MUTED, name="Source")
    add_text(slide, 12.0, 7.02, 0.75, 0.3, [str(number)], size=11, color=MUTED, align=RIGHT, name="Slide number")


def add_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def stat_card(slide, x, y, w, h, number, label, number_color=BLUE, number_size=40, label_size=14, fill=PANEL):
    add_card(slide, x, y, w, h, fill=fill)
    add_text(slide, x + 0.2, y + 0.15, w - 0.4, h * 0.45, [number], size=number_size, bold=True, color=number_color, font=HEAD_FONT,
             anchor=MSO_ANCHOR.MIDDLE)
    add_text(slide, x + 0.2, y + 0.15 + h * 0.45, w - 0.4, h * 0.55 - 0.3, [label], size=label_size, color=INK)


def card_with_text(slide, x, y, w, h, heading, items, fill=PANEL, heading_color=BLUE, text_color=INK, size=14, heading_size=18, bullets=True):
    add_card(slide, x, y, w, h, fill=fill)
    add_text(slide, x + 0.25, y + 0.18, w - 0.5, 0.45, [heading], size=heading_size, bold=True, color=heading_color)
    add_text(slide, x + 0.25, y + 0.7, w - 0.5, h - 0.85,
             [{"text": item, "bullet": bullets} if isinstance(item, str) else item for item in items], size=size, color=text_color, space_after=7)


SRC_ALL = "Sources: Bundesnetzagentur (12.11.2026), KBA (01.01.2026), Destatis (31.12.2024)"

# ------------------------------------------------------------------ 1 title
s = new_slide(dark=True)
add_text(s, 0.7, 1.7, 6.5, 2.4, ["Where does public charging lag behind electric cars?"], size=42, bold=True, font=HEAD_FONT, color=WHITE, name="Title")
add_text(s, 0.7, 4.3, 6.5, 0.6, ["A district level analysis for Germany"], size=22, color=LIGHT_BLUE)
add_text(s, 0.7, 6.4, 6.5, 0.4, ["Florian  |  November 2026"], size=16, color=WHITE)
add_card(s, 7.7, 0.6, 5.0, 6.3, fill=WHITE)
add_image(s, ROOT / "reports" / "gap_map_percent.png", 7.9, 0.75, 4.6, 5.45, name="Map of the gaps")
add_text(s, 7.95, 6.3, 4.5, 0.5, ["Gap between actual and expected charging points per district (red: fewer than expected)"], size=11, color=MUTED, align=CENTER)
add_notes(s, "About 15 seconds. Introduce the question: where does public charging infrastructure lag behind the number of electric cars? "
             "The map on the right is the result, shown in detail later. Red districts have fewer charging points than a typical district of the same size.")

# ------------------------------------------------------------------ 2 question
s = new_slide()
add_title(s, "Cars per charging point range from 3 to 30")
stat_card(s, 0.6, 1.7, 3.9, 2.05, "2.03 million", "battery electric cars registered on 1 January 2026")
stat_card(s, 4.72, 1.7, 3.9, 2.05, "214,398", "public charging points in operation on 12 November 2026")
stat_card(s, 8.84, 1.7, 3.9, 2.05, "9.5", "cars per charging point nationally. Across 399 districts it ranges from 2.9 to 29.8")
add_card(s, 0.6, 4.0, 12.14, 1.15, fill=NAVY)
add_text(s, 0.9, 4.0, 11.6, 1.15, ["Where does public charging lag behind what a typical district of the same size has?"], size=22, bold=True,
         color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
add_text(s, 0.6, 5.5, 3.9, 1.4, [{"text": "Charging operators", "bold": True, "color": BLUE, "size": 20}, "Where to look first when planning sites"], size=17)
add_text(s, 4.72, 5.5, 3.9, 1.4, [{"text": "Municipalities", "bold": True, "color": BLUE, "size": 20}, "How a district compares with similar ones"], size=17)
add_text(s, 8.84, 5.5, 3.9, 1.4, [{"text": "Carmakers", "bold": True, "color": BLUE, "size": 20}, "Where customers may find fewer charging points"], size=17)
add_footer(s, 2, SRC_ALL)
add_notes(s, "About 45 seconds. Nationally there are about 9.5 electric cars per public charging point, but districts range from under 3 to nearly 30. "
             "The question is where a district has fewer charging points than a typical district of the same size. "
             "Three groups could use the answer: operators choosing sites, municipalities comparing themselves, and carmakers.")

# ------------------------------------------------------------------ 3 approach
s = new_slide()
add_title(s, "Approach: a fair yardstick for every district")
steps = [
    ("1  Data", "Three public sources: charging register, car stock, population"),
    ("2  Clean and join", "ETL in Python, totals checked, 399 districts, tested"),
    ("3  Model", "Expected charging points from cars, residents and density"),
    ("4  Gap and ranking", "Actual compared with expected, in percent"),
    ("5  Map, API, Docker", "Offline map, FastAPI service, one Docker build"),
]
box_w, gap = 2.2, 0.28
for index, (name, detail) in enumerate(steps):
    x = 0.6 + index * (box_w + gap)
    add_card(s, x, 1.85, box_w, 1.0, fill=BLUE if index != 2 else NAVY, radius=0.1)
    add_text(s, x + 0.1, 1.85, box_w - 0.2, 1.0, [name], size=17, bold=True, color=WHITE, anchor=MSO_ANCHOR.MIDDLE, align=CENTER)
    add_text(s, x, 3.05, box_w, 1.5, [detail], size=15, color=INK, align=CENTER)
    if index < len(steps) - 1:
        add_arrow(s, x + box_w + 0.03, 2.2)
add_card(s, 0.6, 4.75, 12.14, 2.0)
add_text(s, 0.9, 4.9, 5.6, 1.8, [
    {"text": "In the model", "bold": True, "color": BLUE, "size": 17},
    {"text": "Target: public charging points per district", "bullet": True},
    {"text": "Inputs: battery electric cars, residents, density", "bullet": True},
    {"text": "Evaluation: cross validation against a simple baseline", "bullet": True},
], size=15)
add_text(s, 6.9, 4.9, 5.6, 1.8, [
    {"text": "In the gap", "bold": True, "color": BLUE, "size": 17},
    {"text": "Gap = (actual minus expected) divided by expected", "bullet": True},
    {"text": "Clearly below: more than 30% under expected", "bullet": True},
    {"text": "30% lies above the typical model error of about 21%", "bullet": True},
], size=15)
add_footer(s, 3)
add_notes(s, "About 45 seconds. The whole project in one picture. The key idea is step 3: a ratio of cars per charging point is not a fair yardstick, "
             "so I model what a typical district of the same size has, and compare each district with that number. "
             "The gap is in percent. Only gaps beyond 30% count, because the model itself is about 21% off for a typical district.")

# ------------------------------------------------------------------ 4 data and join
s = new_slide()
add_title(s, "Three public sources and one join that needed care")
add_table(s, 0.6, 1.75, [2.3, 3.3, 1.5], [
    ["Source", "Content", "Date"],
    ["Bundesnetzagentur register", "Public charging stations with number of points and district name", "12.11.2026"],
    ["KBA table FZ 1.2", "Passenger cars per district by fuel type, battery electric separate", "01.01.2026"],
    ["Destatis", "Area and population per Kreis, Zensus 2022 basis", "31.12.2024"],
], row_height=0.92, size=14)
add_text(s, 0.6, 5.45, 7.1, 0.5, ["Result: one table with 399 districts"], size=20, bold=True, color=BLUE)
add_text(s, 0.6, 6.0, 7.1, 0.8, ["The three reference dates differ: cars are about 10 months older than the charging points."], size=14, color=MUTED)
card_with_text(s, 8.0, 1.75, 4.74, 5.05, "The join problem", [
    "The register names districts as text and has no keys",
    "A city and its Landkreis often share a name, for example Passau, Hof and Rosenheim",
    "A first match on the name alone gave 442 matches for 401 names. Points were counted twice, and these cities looked best supplied",
    "Fix: match type and name, one rule for Hanau, merge Trier with Trier-Saarburg",
    "Check: totals before and after the join are equal (214,398 points, 2,031,870 cars)",
], size=16)
add_footer(s, 4)
add_notes(s, "About 75 seconds. Three public sources, free to download. The hard part was the join: the register only has district names. "
             "A city and its surrounding Landkreis often share a name. My first match counted points twice, and cities like Passau looked like the best supplied places in Germany, "
             "which is wrong. I fixed the match, and the pipeline now stops if any car, person or charging point is lost or duplicated in the join.")

# ------------------------------------------------------------------ 5 insight
s = new_slide()
add_title(s, "Charging points follow residents as much as cars")
add_image(s, FIGURES / "insight_scatter.png", 0.6, 1.7, 7.5, 4.6, name="Charging points against electric cars")
card_with_text(s, 8.4, 1.7, 4.34, 2.15, "Variation explained (R2)", [
    {"text": [("Cars only  ", {}), ("0.78", {"bold": True, "color": BLUE})], "size": 16},
    {"text": [("Residents only  ", {}), ("0.76", {"bold": True, "color": BLUE})], "size": 16},
    {"text": [("Both  ", {}), ("0.81", {"bold": True, "color": BLUE})], "size": 16},
], bullets=False)
card_with_text(s, 8.4, 4.05, 4.34, 2.25, "Cars per charging point", [
    {"text": [("Smallest third of districts  ", {}), ("7.4", {"bold": True, "color": BLUE})], "size": 16},
    {"text": [("Middle third  ", {}), ("9.4", {"bold": True, "color": BLUE})], "size": 16},
    {"text": [("Largest third  ", {}), ("10.0", {"bold": True, "color": BLUE})], "size": 16},
], bullets=False)
add_text(s, 0.6, 6.4, 12.1, 0.55, ["So the plain ratio flags large districts partly because they are large. That is why I model an expected number."],
         size=17, bold=True, color=NAVY)
add_footer(s, 5, "In-sample check on 399 districts. Cars and residents correlate at 0.89, so the split between them is rough. Source: notebook 01, section 7")
add_notes(s, "About 75 seconds. This is the main data insight. Charging points grow slower than electric cars: the blue line is flatter than the dashed proportional line. "
             "Residents explain the number of charging points almost as well as electric cars do. Together they explain 81% of the variation. "
             "Consequence: large districts show more cars per point just because they are large, 7.4 in the smallest third and 10.0 in the largest. "
             "A ranking by the plain ratio would flag big districts for the wrong reason. This is a first look on all districts, the model step tests it properly.")

# ------------------------------------------------------------------ 6 method
s = new_slide()
add_title(s, "Method: three models, tested on unseen districts")
card_with_text(s, 0.6, 1.7, 3.9, 2.35, "Baseline ratio", [
    {"text": "Expected points = cars divided by the national cars per charging point. The ratio is learned on training districts only", "size": 16},
], bullets=False)
card_with_text(s, 4.72, 1.7, 3.9, 2.35, "Linear regression on logs", [
    {"text": "The main model. Inputs: cars, residents, density. It works in percentages: 10% more cars means about 5% more points", "size": 16, "color": WHITE},
], fill=BLUE, heading_color=WHITE, bullets=False)
card_with_text(s, 8.84, 1.7, 3.9, 2.35, "Gradient boosting", [
    {"text": "The comparison. 200 shallow trees, small fixed settings, not tuned. It can find curves that the linear model misses", "size": 16},
], bullets=False)
card_with_text(s, 0.6, 4.3, 5.95, 2.5, "Evaluation", [
    "5-fold cross validation: every district is predicted by a model that never saw it",
    "A second test holds out whole federal states",
    "Every model is compared with the baseline in every fold",
], size=16)
card_with_text(s, 6.79, 4.3, 5.95, 2.5, "Guards against leakage", [
    "A column built from the target (cars per point) was removed from the pipeline",
    "A test checks that a district cannot change its own expected value",
    "The baseline ratio is computed per training fold",
], size=16)
add_footer(s, 6)
add_notes(s, "About 60 seconds. Three models: a simple ratio as the baseline, a linear regression on logs as the main model, and gradient boosting to see whether a flexible model finds something extra. "
             "The important part is the evaluation. Each district's expected value comes from a model that did not see that district. "
             "I also found and removed a column that contained the target, and I wrote tests so that a district cannot influence its own expected value.")

# ------------------------------------------------------------------ 7 results
s = new_slide()
add_title(s, "The simple model wins with a typical error of 21%")
data = CategoryChartData()
data.categories = ["Random folds", "Folds by federal state"]
data.add_series("Baseline ratio", (26.6, 28.2))
data.add_series("Gradient boosting", (22.6, 23.9))
data.add_series("Linear regression on logs", (21.1, 22.9))
chart_frame = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.6), Inches(7.0), Inches(5.2), data)
chart_frame.name = "Typical error by model"
chart = chart_frame.chart
chart.has_title = True
chart.chart_title.text_frame.text = "Typical error per district, %"
chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(16)
chart.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
chart.chart_title.text_frame.paragraphs[0].runs[0].font.name = BODY_FONT
chart.has_legend = True
chart.legend.position = XL_LEGEND_POSITION.BOTTOM
chart.legend.include_in_layout = False
chart.legend.font.size = Pt(14)
chart.legend.font.name = BODY_FONT
plot = chart.plots[0]
plot.gap_width = 70
plot.has_data_labels = True
labels = plot.data_labels
labels.font.size, labels.font.bold, labels.font.name = Pt(14), True, BODY_FONT
labels.number_format, labels.number_format_is_linked = '0.0"%"', False
labels.position = XL_LABEL_POSITION.OUTSIDE_END
for series, colour in zip(plot.series, (GREY, LIGHT_BLUE, BLUE)):
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = rgb(colour)
axis = chart.value_axis
axis.minimum_scale, axis.maximum_scale = 0, 35
axis.has_major_gridlines = True
axis.major_gridlines.format.line.color.rgb = rgb("D9D9D9")
axis.tick_labels.font.size = Pt(12)
axis.format.line.fill.background()
chart.category_axis.tick_labels.font.size = Pt(14)
add_text(s, 7.95, 1.75, 4.8, 5.0, [
    {"text": "Linear model beats the baseline in 5 of 5 folds and in 10 of 10 repeated splits, by 5 to 7 points", "bullet": True},
    {"text": "Gradient boosting brings no clear gain and ranks districts almost the same (rank correlation 0.92)", "bullet": True},
    {"text": "Plug-in hybrids as an extra input change neither the error nor the ranking (rank correlation 0.996 or higher)", "bullet": True},
    {"text": "A typical error of 21% means only large gaps count", "bullet": True, "bold": True, "color": NAVY},
], size=18, space_after=16)
add_footer(s, 7, "Typical error = median of |expected minus actual| divided by actual, 5-fold cross validation. Source: notebooks 02 and 03")
add_notes(s, "About 60 seconds. The linear model on logs has the lowest error in both tests, about 21% with random folds and 23% when whole federal states are held out. "
             "The baseline is about 27% off. It wins in every fold and in ten repeated splits. Gradient boosting does not find anything the simple model misses, "
             "and I tested plug-in hybrids as an extra input: no gain. So I keep the simple model, which is also easier to explain. "
             "The honest message: a typical error of 21% means a gap of minus 20% is noise.")

# ------------------------------------------------------------------ 8 states
s = new_slide()
add_title(s, "Federal states differ from what the model expects")
states = [("Hamburg", 43, 1), ("Mecklenburg-Vorpommern", 32, 8), ("Berlin", 27, 1), ("Baden-Württemberg", 15, 44),
          ("Schleswig-Holstein", 14, 15), ("Bayern", 10, 96), ("Thüringen", 9, 22), ("Sachsen-Anhalt", 3, 14), ("Sachsen", 2, 13),
          ("Brandenburg", 2, 18), ("Bremen", -3, 2), ("Niedersachsen", -4, 45), ("Hessen", -6, 26), ("Nordrhein-Westfalen", -13, 53),
          ("Rheinland-Pfalz", -24, 35), ("Saarland", -35, 6)]
state_data = CategoryChartData()
state_data.categories = [f"{name} (n={count})" for name, _, count in states]
# Two series (above and below expected) with a bar overlap of 100%. A single series with a colour per bar is drawn wrongly
# by some viewers, which show negative bars as positive ones.
state_data.add_series("Above expected", [value if value > 0 else None for _, value, _ in states])
state_data.add_series("Below expected", [value if value < 0 else None for _, value, _ in states])
state_frame = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.55), Inches(7.4), Inches(5.35), state_data)
state_frame.name = "Average gap by federal state"
state_chart = state_frame.chart
state_chart.has_legend = True
state_chart.legend.position = XL_LEGEND_POSITION.BOTTOM
state_chart.legend.include_in_layout = False
state_chart.legend.font.size = Pt(12)
state_chart.legend.font.name = BODY_FONT
state_chart.has_title = True
state_chart.chart_title.text_frame.text = "Average gap of the districts in each state, % of expected (n = districts)"
title_run = state_chart.chart_title.text_frame.paragraphs[0].runs[0]
title_run.font.size, title_run.font.bold, title_run.font.name = Pt(14), True, BODY_FONT
state_plot = state_chart.plots[0]
state_plot.gap_width = 40
state_plot.overlap = 100
state_plot.vary_by_categories = False
state_plot.has_data_labels = True
state_labels = state_plot.data_labels
state_labels.font.size, state_labels.font.bold, state_labels.font.name = Pt(12), True, BODY_FONT
state_labels.number_format, state_labels.number_format_is_linked = '+0"%";-0"%"', False
state_labels.position = XL_LABEL_POSITION.OUTSIDE_END
for series, colour in zip(state_plot.series, (LIGHT_BLUE, BLUE)):
    series.invert_if_negative = False
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = rgb(colour)
state_chart.category_axis.reverse_order = True
state_chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
state_chart.category_axis.tick_labels.font.size = Pt(12)
state_chart.category_axis.format.line.color.rgb = rgb(MUTED)
state_chart.value_axis.minimum_scale, state_chart.value_axis.maximum_scale = -50, 55
state_chart.value_axis.has_major_gridlines = False
# The axis stays in the chart (a deleted axis is drawn wrongly by some viewers). Its labels and line are hidden.
state_chart.value_axis.tick_label_position = XL_TICK_LABEL_POSITION.NONE
state_chart.value_axis.major_tick_mark = XL_TICK_MARK.NONE
state_chart.value_axis.format.line.fill.background()
add_text(s, 8.3, 1.75, 4.45, 3.4, [
    {"text": "Saarland is 35% below expected on average, Rheinland-Pfalz 24% below", "bullet": True},
    {"text": "Hamburg, Mecklenburg-Vorpommern and Berlin are above. Hamburg and Berlin are one district each", "bullet": True},
    {"text": "The model does not know the state, so these patterns stay in the gaps", "bullet": True},
    {"text": "The data does not show why", "bullet": True},
], size=17, space_after=10)
add_card(s, 8.3, 5.35, 4.45, 1.45)
add_text(s, 8.5, 5.35, 4.05, 1.45, ["No bias by district size: the average residual stays between -0.02 and +0.02 in all five size groups"], size=15,
         color=INK, anchor=MSO_ANCHOR.MIDDLE)
add_footer(s, 8, "Out of fold gaps of the linear model. Source: notebook 02")
add_notes(s, "About 30 seconds. Checking the residuals showed a pattern I did not model: whole federal states sit above or below the expected value. "
             "Saarland and Rheinland-Pfalz are clearly below, Hamburg and Berlin are above, but those two are single districts. "
             "The data does not tell why. It matters for the ranking, because many districts of Rheinland-Pfalz and Saarland end up at the top. "
             "On the other hand, the model has no bias by district size.")

# ------------------------------------------------------------------ 9 where
s = new_slide()
add_title(s, "55 of 399 districts are clearly below expected")
add_image(s, ROOT / "reports" / "gap_map_percent.png", 0.6, 1.65, 4.9, 5.25, name="Map of the gaps")
add_table(s, 5.8, 1.7, [1.7, 0.75, 0.9], [
    ["Largest gap", "Gap", "Missing"],
    ["Kusel", "-60%", "90"],
    ["Südwestpfalz", "-58%", "122"],
    ["Germersheim", "-54%", "181"],
    ["Wolfenbüttel", "-52%", "160"],
    ["Altenkirchen", "-50%", "162"],
], row_height=0.46, size=14, align_right_from=1)
add_table(s, 9.5, 1.7, [1.85, 0.8, 0.6], [
    ["Most missing points", "Points", "Gap"],
    ["München", "1,817", "-37%"],
    ["Rhein-Sieg-Kreis", "476", "-32%"],
    ["Rhein-Neckar-Kreis", "405", "-25%"],
    ["Euskirchen", "363", "-48%"],
    ["Rhein-Erft-Kreis", "355", "-31%"],
], row_height=0.46, size=14, align_right_from=1)
stat_card(s, 5.8, 4.7, 2.1, 2.1, "42 of 55", "also flagged by gradient boosting", number_size=26, label_size=14)
stat_card(s, 8.08, 4.7, 2.1, 2.1, "2 of 15", "districts in both top 15 lists", number_size=26, label_size=14)
stat_card(s, 10.36, 4.7, 2.38, 2.1, "35%", "of the 55 are in Rheinland-Pfalz or Saarland (10% of all districts)", number_size=26, label_size=14)
add_footer(s, 9, "Clearly below: more than 30% under expected. Missing = expected minus actual charging points. Source: notebook 04")
add_notes(s, "About 75 seconds. 55 of 399 districts are more than 30% below their expected number, and for 42 of them gradient boosting agrees. "
             "There are two views. By percent, small districts such as Kusel and Südwestpfalz come first. By missing points, München is first with about 1,800, "
             "even though it is only rank 30 by percent. Only 2 of the top 15 appear in both lists, so which view to use depends on the question: "
             "a municipality comparing itself with peers looks at percent, an operator choosing sites looks at points.")

# ------------------------------------------------------------------ 10 value
s = new_slide()
add_title(s, "Closing the gaps: about 27 to 125 million EUR")
add_table(s, 0.6, 1.7, [3.3, 1.35, 1.75, 1.6], [
    ["Closing the gap", "Missing points", "Investment, million EUR", "Gross revenue per year, million EUR"],
    ["To the edge of the band (70% of expected)", "2,278", "27 (21 to 54)", "11 (4 to 23)"],
    ["To the expected number", "10,423", "125 (98 to 249)", "51 (20 to 104)"],
], row_height=0.9, size=14, align_right_from=1)
add_text(s, 0.6, 4.55, 8.0, 0.4, ["Base case, with low to high in brackets"], size=14, color=MUTED)
add_card(s, 0.6, 5.0, 8.0, 0.85)
add_text(s, 0.85, 5.0, 7.5, 0.85, ["Scale from observed data: 35,754 charging points were commissioned in 2025. The missing points are 0.8 and 3.5 months of that."],
         size=14, anchor=MSO_ANCHOR.MIDDLE)
add_card(s, 0.6, 6.0, 8.0, 0.85, fill=NAVY)
add_text(s, 0.85, 6.0, 7.5, 0.85, ["Revenue is gross: electricity, operation, rent and tax are not subtracted. An order of magnitude, not a business case."],
         size=14, bold=True, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
add_card(s, 8.9, 1.7, 3.84, 5.15)
add_text(s, 9.15, 1.85, 3.4, 0.45, ["How solid are the numbers?"], size=20, bold=True, color=BLUE)
add_text(s, 9.15, 2.5, 3.4, 4.3, [
    {"text": "Sourced", "bold": True, "color": NAVY, "size": 17, "space_after": 2},
    {"text": "Investment per point (Öko-Institut, EWI, FCN, 2022). Ad hoc prices (ACE, 2026)", "size": 16, "space_after": 16},
    {"text": "Unverified", "bold": True, "color": NAVY, "size": 17, "space_after": 2},
    {"text": "Charging sessions per point and day. Seen in a search summary only", "size": 16, "space_after": 16},
    {"text": "Guesses", "bold": True, "color": RED, "size": 17, "space_after": 2},
    {"text": "Use of new points, energy per session, share of the price paid", "size": 16},
])
add_footer(s, 10, "Source: notebook 04, assumptions A8 to A14 in the README")
add_notes(s, "About 75 seconds. This is deliberately rough. Closing the gaps of the 55 districts to the edge of the band needs about 2,300 charging points, about 27 million euros in the base case. "
             "Closing them to the expected number needs about 10,400 points, about 125 million. For scale: the market built about 35,000 points in 2025, so the smaller case is under one month of that. "
             "Be clear about the assumptions: investment per point comes from a 2022 study, prices from a 2026 survey, and some inputs are guesses. Revenue is gross and is not profit.")

# ------------------------------------------------------------------ 11 prototype
s = new_slide()
add_title(s, "Prototype: map, API and one Docker command")
flow = [("Download script", "Four public files"), ("Pipeline, model, ranking, map", "Tested steps"),
        ("Finished files", "Model, ranking table, map"), ("FastAPI service and page", "District lookup, what-if")]
w4, g4 = 2.85, 0.247
for index, (name, detail) in enumerate(flow):
    x = 0.6 + index * (w4 + g4)
    add_card(s, x, 1.7, w4, 0.95, fill=BLUE, radius=0.1)
    add_text(s, x + 0.1, 1.7, w4 - 0.2, 0.95, [name], size=16, bold=True, color=WHITE, anchor=MSO_ANCHOR.MIDDLE, align=CENTER)
    add_text(s, x, 2.75, w4, 0.4, [detail], size=14, color=INK, align=CENTER)
    if index < 3:
        add_arrow(s, x + w4 + 0.02, 2.0)
add_table(s, 0.6, 3.45, [3.3, 3.4], [
    ["Endpoint", "Returns"],
    ["GET /districts/{key}", "Gap of one district"],
    ["GET /expected?bev&population&density", "What-if estimate"],
    ["GET /districts", "List for a drop-down"],
    ["GET /health", "Status, error, data dates"],
], row_height=0.56, size=15)
add_card(s, 7.6, 3.45, 5.14, 1.55, fill=NAVY)
add_text(s, 7.8, 3.55, 4.8, 1.35, [
    {"text": "docker build -t ev-gap .", "font": MONO_FONT, "size": 14, "color": WHITE, "space_after": 8},
    {"text": "docker run --rm -p 8000:8000 ev-gap", "font": MONO_FONT, "size": 14, "color": WHITE},
], anchor=MSO_ANCHOR.MIDDLE)
add_text(s, 7.6, 5.15, 5.14, 1.7, [
    {"text": "The build runs 83 tests, trains the model and ships only the finished files", "bullet": True},
    {"text": "The map is one HTML file that works offline", "bullet": True},
], size=15, space_after=6)
add_card(s, 0.6, 6.4, 7.3, 0.55)
add_text(s, 0.8, 6.4, 6.9, 0.55, ["Without Docker: uv sync, then the commands in the README run every step"], size=14, anchor=MSO_ANCHOR.MIDDLE)
add_footer(s, 11)
add_notes(s, "About 45 seconds. The prototype has three parts. A map, one HTML file that works offline. A small FastAPI service with the gap of a district and a what-if endpoint. "
             "And a Docker image: the build stage downloads the data, runs 83 tests, trains the model and builds the map, and the final image only holds the finished files. "
             "So someone with only Docker can run the service with two commands.")

# ------------------------------------------------------------------ 12 demo
s = new_slide()
add_title(s, "Demo: from the map to a single district")
add_image(s, ROOT / "reports" / "gap_map_percent.png", 0.6, 1.65, 4.6, 5.25, name="Map of the gaps")
add_card(s, 5.5, 1.65, 7.24, 1.6)
add_text(s, 5.75, 1.7, 6.8, 1.5, [
    {"text": "1  Switch the view in the map drop-down", "space_after": 3},
    {"text": "2  Hover over a district", "space_after": 3},
    {"text": "3  Look up Kusel in the page", "space_after": 3},
    {"text": "4  Ask the what-if question", "space_after": 3},
], size=16, anchor=MSO_ANCHOR.MIDDLE)
add_card(s, 5.5, 3.4, 3.55, 3.45, fill=NAVY)
add_text(s, 5.7, 3.5, 3.2, 3.3, [
    {"text": "GET /districts/07336", "bold": True, "color": LIGHT_BLUE, "space_after": 6},
    "Kusel (Rheinland-Pfalz)",
    "actual 60",
    "expected 150.2",
    "gap -60.1%",
    "missing 90.2",
    "robust: yes",
    "rank 1 (percent)",
    "rank 79 (points)",
], size=14, font=MONO_FONT, color=WHITE, space_after=3)
add_card(s, 9.19, 3.4, 3.55, 3.45, fill=NAVY)
add_text(s, 9.39, 3.5, 3.2, 3.3, [
    {"text": "GET /expected", "bold": True, "color": LIGHT_BLUE, "space_after": 6},
    "population 69,334",
    "density 121 per km2",
    {"text": "bev 1,262 gives 150.0", "space_after": 8},
    {"text": "bev 2,524 gives 209.2", "space_after": 8},
    "Twice the cars gives about 40% more expected points",
], size=14, font=MONO_FONT, color=WHITE, space_after=3)
add_footer(s, 12, "Real answers of the running service for Kusel (key 07336) and for the what-if inputs of Kusel")
add_notes(s, "About 60 seconds. This slide is the script for the demo. Open the map, switch between the three views with the drop-down, hover over a district to see actual and expected charging points. "
             "Then the service: look up Kusel, which has 60 charging points against 150 expected, a gap of minus 60%. "
             "Then the what-if question: with the inputs of Kusel the model returns 150 points, with twice the cars it returns 209, about 40% more, "
             "because charging points grow only about half as fast as cars. The values on this slide are real answers of the service.")

# ------------------------------------------------------------------ 13 limits
s = new_slide()
add_title(s, "Limits, and how I would extend it")
card_with_text(s, 0.6, 1.7, 5.95, 5.1, "What the result does not show", [
    "A typical error of about 21%: a gap of -20% is noise",
    "It describes today's relationship. It does not show how many charging points are optimal",
    "Cars are counted where they are registered, not where they are charged",
    "There are no utilization data, so below expected does not mean more are needed",
    "The value estimate rests on assumptions, some of them guesses",
    "Reference dates differ between the sources",
], size=17)
card_with_text(s, 6.79, 1.7, 5.95, 5.1, "How I would extend it", [
    "Refresh the data and retrain on a schedule, with checks before a new model goes live",
    "Track runs and models (MLflow) once there are many",
    "Monitor the typical error and the gaps over time",
    "Add utilization data and commuter flows",
    "Outlook model: predict electric car growth per district, tested by time (designed, not built)",
    "Build and test on every change (CI)",
], size=17)
add_footer(s, 13)
add_notes(s, "About 45 seconds. Limits first. The model is about 21% off for a typical district, so only large gaps matter. It shows where a district is unusual compared with similar ones, "
             "not where charging points are needed: utilization data is missing, and cars are counted where they are registered. "
             "For scaling: refresh the data and retrain with checks, track runs with MLflow, monitor the error over time, add utilization data, "
             "and an outlook model for electric car growth, which I designed but did not build.")

# ------------------------------------------------------------------ 14 AI
s = new_slide()
add_title(s, "How I used AI tools")
card_with_text(s, 0.6, 1.7, 5.95, 5.1, "What the assistant did", [
    "Claude Code (Anthropic) as a coding assistant",
    "Researched data sources, wrote the pipeline, models, tests, notebooks, map, API, Dockerfile and drafts of the README",
    "Ran the tests and the pipeline to check its own statements, and corrected them when the numbers disagreed",
    "Found and fixed errors of its own: a join that counted points twice, a wrong claim about the model fit, an oversized image",
], size=17)
card_with_text(s, 6.79, 1.7, 5.95, 5.1, "What I decided and checked", [
    "The question, the scope and what to leave out (MLflow, the outlook model)",
    "Model choice: linear regression on logs, gradient boosting as comparison, gap in percent",
    "Extra checks: leakage review, plug-in hybrid test, evaluation by federal state",
    "In place: 83 automatic tests, totals that must reconcile, map and service opened in a browser",
], size=17)
add_footer(s, 14, "Details per step are in the README, section on AI tools")
add_notes(s, "About 30 seconds. Be open about the tools. Claude Code wrote much of the code, the tests and the drafts. I set the question and the scope, chose the models and the way to report the gap, "
             "asked for the leakage review and the extra checks, and decided what to drop for time. Several errors were found and fixed along the way, for example the join that counted points twice. "
             "Adjust this slide so that it says exactly what you did and checked yourself.")

# ------------------------------------------------------------------ 15 summary
s = new_slide(dark=True)
add_text(s, 0.7, 0.5, 11.5, 0.8, ["Summary"], size=36, bold=True, font=HEAD_FONT, color=WHITE, name="Title")
points = [
    "Charging points follow residents about as much as cars, so the plain ratio is a biased yardstick",
    "A simple, cross validated model gives a fair yardstick, with a typical error of 21%",
    "55 of 399 districts are clearly below expected. Percent and absolute numbers name different districts",
    "The value is an order of magnitude: 27 to 125 million EUR in the base case, built from marked assumptions",
]
for index, point in enumerate(points):
    y = 1.65 + index * 1.15
    circle = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.7), Inches(y), Inches(0.7), Inches(0.7))
    circle.fill.solid()
    circle.fill.fore_color.rgb = rgb(LIGHT_BLUE)
    circle.line.fill.background()
    circle.shadow.inherit = False
    add_text(s, 0.7, y, 0.7, 0.7, [str(index + 1)], size=22, bold=True, color=NAVY, align=CENTER, anchor=MSO_ANCHOR.MIDDLE)
    add_text(s, 1.65, y - 0.05, 10.9, 0.8, [point], size=20, color=WHITE, anchor=MSO_ANCHOR.MIDDLE)
add_text(s, 0.7, 6.35, 11.5, 0.7, ["Thank you. Questions?"], size=28, bold=True, font=HEAD_FONT, color=LIGHT_BLUE)
add_notes(s, "About 30 seconds, then questions. Four messages: the ratio is biased because charging points follow residents as much as cars; a simple cross validated model is a fair yardstick; "
             "55 districts are clearly below, and the percent and absolute views differ; the value is an order of magnitude from marked assumptions. "
             "The appendix has the data issues, the value assumptions and the engineering details.")

# ------------------------------------------------------------------ appendix A1
s = new_slide()
add_title(s, "Appendix: data issues found and handled")
add_text(s, 0.6, 1.7, 12.1, 5.1, [
    {"text": "Register CSV: ten lines before the header, a decimal comma, and not UTF-8 (cp1252)", "bullet": True},
    {"text": "District names without keys: match on type and name, one rule for Hanau", "bullet": True},
    {"text": "KBA and Destatis differ for Hanau, and for Trier with Trier-Saarburg: merged, with assumptions A1 and A2 in the README", "bullet": True},
    {"text": "29 stations in maintenance (55 charging points) are not counted", "bullet": True},
    {"text": "One coordinate outside Germany, and 231 stations above 400 kW (probably station totals, not verified)", "bullet": True},
    {"text": "Reference dates differ: cars 01.01.2026, charging points 12.11.2026, population 31.12.2024", "bullet": True},
    {"text": "The totals check stops the pipeline if the join loses or duplicates cars, people or charging points", "bullet": True},
], size=18, space_after=14)
add_footer(s, 16, "Source: README, steps 3 and 4")

# ------------------------------------------------------------------ appendix A2
s = new_slide()
add_title(s, "Appendix: value assumptions and their sources")
add_table(s, 0.6, 1.65, [0.75, 6.35, 5.0], [
    ["Id", "Assumption", "Source or status"],
    ["A8", "Clearly below = more than 30% under expected", "Above the typical model error of 21%"],
    ["A9", "New points have the national mix (28.5% fast)", "Observed in the register"],
    ["A10", "Investment per point: normal 4,000 to 7,500 EUR, fast 23,000 to 65,000 EUR", "Öko-Institut, EWI, FCN, 2022, table 2-1. No VAT, no grid expansion"],
    ["A11", "Sessions per point and day: 0.63 normal, 2.5 fast", "Statista page, search summary only, unverified"],
    ["A12", "New points are used at 50%, 75% or 100% of the average", "Guess"],
    ["A13", "Energy per session: 10 to 20 kWh normal, 25 to 45 kWh fast", "Guess"],
    ["A14", "Price: ad hoc average 52.3 ct (AC) and 70.5 ct (DC), 70% to 100% paid", "ACE, July 2026 (search summary). The factors are guesses"],
], row_height=0.66, size=14)
add_footer(s, 17, "Source: README, assumptions A8 to A14")

# ------------------------------------------------------------------ appendix A3
s = new_slide()
add_title(s, "Appendix: engineering")
card_with_text(s, 0.6, 1.7, 3.9, 4.9, "Pipeline (ETL)", [
    "About 120,000 register rows and 400 districts, no warehouse",
    "The hard parts are the Excel layout and the name matching: pandas and tests fit",
    "Settings, reading, rules and writing are in separate modules",
], size=16)
card_with_text(s, 4.72, 1.7, 3.9, 4.9, "Tests (83)", [
    "Key mapping, sheet parsing, cleaning, leakage guards",
    "Model evaluation, ranking and value arithmetic",
    "Map views, API answers and input limits",
    "One end to end test on the real files",
], size=16)
card_with_text(s, 8.84, 1.7, 3.9, 4.9, "Docker", [
    "Two stage build: data, tests, pipeline and model in stage 1",
    "Stage 2 holds only the code and the finished files",
    "Runs as a normal user, with a health check",
    "Removing uv's cache cut the image from 1.47 GB to 960 MB",
], size=16)
add_footer(s, 18, "Source: README, steps 4, 7 and 7a")

prs.save(OUTPUT)
print(f"saved {OUTPUT} with {len(prs.slides)} slides")
