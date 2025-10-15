"""
pdf_to_latex_map.py

- Convert pages -> images into temp_pages/
- Use chrome_lens_py LensAPI with output_format='detailed' to get geometry
- Heuristic detect LaTeX-like blocks; crop & save images for each formula.
- (Optional) call pix2tex / LaTeXOCR models on the crop if installed.
- Output a JSON-like report printed to stdout and saved to 'latex_report.json'.
"""

import os
import asyncio
import json
import re
from tempfile import NamedTemporaryFile
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageOps, ImageFilter
import cv2
import numpy as np

from chrome_lens_py.api import LensAPI
from chrome_lens_py.constants import DEFAULT_API_KEY

# Optional: try to import pix2tex or pix2text model; ignore if not available
try:
    # pix2tex / LaTeX-OCR style
    from pix2tex.cli import LatexOCR as Pix2TexOCR
    PIX2TEX_AVAILABLE = True
    pix2tex_model = Pix2TexOCR()
except Exception:
    pix2tex_model = None
    PIX2TEX_AVAILABLE = False

# rapid-latex package has class LaTeXOCR (note capital X)
try:
    from rapid_latex_ocr import LaTeXOCR
    rapid_model = LaTeXOCR()
    RAPID_AVAILABLE = True
except Exception:
    rapid_model = None
    RAPID_AVAILABLE = False

OUT_DIR = Path("temp_pages")
OUT_DIR.mkdir(exist_ok=True)

# heuristics to decide "formula-looking" text
LATEX_HINT_RE = re.compile(r"[\\\{\}_\^\%]|frac|sqrt|sum|int|\\begin|\\end|\$|\\\[|\\\]", re.I)
# symbols that often appear in math: ∑ ∫ ± ≤ ≥ ∞ ⇒  (some may be OCRed oddly)
MATH_SYMBOLS = set("∑∫±≤≥∞⇒⇒→←≈≡√")

async def ocr_with_lens(image_path):
    api = LensAPI(api_key=DEFAULT_API_KEY)
    try:
        # use detailed output so we get blocks/lines/words + geometry
        res = await api.process_image(image_path=image_path, output_format="detailed", ocr_language="vi", ocr_preserve_line_breaks=True)
        return res
    except Exception as e:
        print("Lens OCR error:", e)
        return None

def preprocess_for_ocr(img_path):
    """Simple preprocessing: grayscale, autocontrast, denoise"""
    im = Image.open(img_path).convert("L")
    im = ImageOps.autocontrast(im)
    im = im.filter(ImageFilter.MedianFilter(size=3))
    im.save(img_path)

def bbox_from_geometry(geom, image_w, image_h):
    """
    Expect geom to be either dict with 'x','y','w','h' or polygon list of points [{x:,y:},...]
    Return (x0,y0,x1,y1) in integer pixel coords (clipped)
    """
    if geom is None:
        return None
    # common shapes: list of points or dict
    if isinstance(geom, dict):
        # maybe normalized? assume pixels
        x = int(geom.get("x", 0))
        y = int(geom.get("y", 0))
        w = int(geom.get("w", 0))
        h = int(geom.get("h", 0))
        x0, y0, x1, y1 = x, y, x + w, y + h
    elif isinstance(geom, (list, tuple)):
        # list of points
        xs = [int(round(p.get("x", p[0]) if isinstance(p, dict) else p[0])) for p in geom]
        ys = [int(round(p.get("y", p[1]) if isinstance(p, dict) else p[1])) for p in geom]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
    else:
        return None
    # clip
    x0 = max(0, min(image_w - 1, x0))
    y0 = max(0, min(image_h - 1, y0))
    x1 = max(0, min(image_w, x1))
    y1 = max(0, min(image_h, y1))
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)

def crop_and_save(image_path, bbox, out_path):
    x0,y0,x1,y1 = bbox
    img = Image.open(image_path)
    crop = img.crop((x0,y0,x1,y1))
    crop.save(out_path)
    return out_path

def detect_formula_by_image(image_path):
    """
    Fallback: run simple OpenCV morphology to find dense symbol regions (likely formulas)
    Return list of bbox tuples.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    # binarize
    _, th = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # invert so text=white
    th = 255 - th
    # dilate to connect symbols
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15,3))
    dil = cv2.dilate(th, kernel, iterations=1)
    contours, _ = cv2.findContours(dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    h, w = img.shape
    for c in contours:
        x,y,ww,hh = cv2.boundingRect(c)
        # heuristic: ignore very small or full-page boxes
        if ww < 20 or hh < 10 or ww > 0.95*w or hh > 0.95*h:
            continue
        boxes.append((x,y,x+ww,y+hh))
    # sort left->right,top->bottom
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    return boxes

async def process_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    report = {"pages": []}

    for i in range(len(doc)):
        page = doc.load_page(i)
        # render page as image (high DPI)
        pix = page.get_pixmap(dpi=400)
        page_img_path = str(OUT_DIR / f"page_{i}.png")
        pix.save(page_img_path)

        # optional preprocess
        preprocess_for_ocr(page_img_path)

        # Lens OCR (detailed)
        res = await ocr_with_lens(page_img_path)
        page_w, page_h = pix.width, pix.height

        page_entry = {
            "page_index": i,
            "image_path": page_img_path,
            "text_blocks": [],
            "latex_candidates": []
        }

        if res is None:
            print(f"Lens returned no result for page {i}")
            report["pages"].append(page_entry)
            continue

        # 1) parse blocks/lines/words if present
        # The library returns keys like 'text_blocks' and each block has 'geometry','text','lines'...
        text_blocks = res.get("text_blocks") or res.get("blocks") or []
        # fallback: if no blocks, use 'ocr_text' (string)
        if not text_blocks and res.get("ocr_text"):
            page_entry["ocr_text"] = res.get("ocr_text")

        for bidx, block in enumerate(text_blocks):
            bgeom = block.get("geometry")
            bbox = bbox_from_geometry(bgeom, page_w, page_h)
            text = block.get("text", "").strip()
            page_entry["text_blocks"].append({
                "block_index": bidx,
                "text": text,
                "geometry": bgeom,
                "bbox": bbox
            })

            # Heuristic: if the block text contains LaTeX hints -> mark candidate
            if LATEX_HINT_RE.search(text) or any(ch in MATH_SYMBOLS for ch in text):
                # save cropped image for this block
                if bbox:
                    crop_path = str(OUT_DIR / f"page_{i}_block_{bidx}.png")
                    crop_and_save(page_img_path, bbox, crop_path)
                    page_entry["latex_candidates"].append({
                        "source": "text_block",
                        "block_index": bidx,
                        "text": text,
                        "bbox": bbox,
                        "crop_image": crop_path,
                        "latex": None  # to fill if model available
                    })

            # also check lines within block if available
            for lidx, line in enumerate(block.get("lines", [])):
                lgeom = line.get("geometry")
                lbbox = bbox_from_geometry(lgeom, page_w, page_h)
                ltext = line.get("text", "").strip()
                if LATEX_HINT_RE.search(ltext) or any(ch in MATH_SYMBOLS for ch in ltext):
                    if lbbox:
                        crop_path = str(OUT_DIR / f"page_{i}_block{bidx}_line{lidx}.png")
                        crop_and_save(page_img_path, lbbox, crop_path)
                        page_entry["latex_candidates"].append({
                            "source": "line",
                            "block_index": bidx,
                            "line_index": lidx,
                            "text": ltext,
                            "bbox": lbbox,
                            "crop_image": crop_path,
                            "latex": None
                        })

                # try words
                for widx, word in enumerate(line.get("words", [])):
                    wtext = word.get("word", "").strip()
                    wgeom = word.get("geometry")
                    wbbox = bbox_from_geometry(wgeom, page_w, page_h)
                    if LATEX_HINT_RE.search(wtext) or any(ch in MATH_SYMBOLS for ch in wtext):
                        if wbbox:
                            crop_path = str(OUT_DIR / f"page_{i}_block{bidx}_line{lidx}_word{widx}.png")
                            crop_and_save(page_img_path, wbbox, crop_path)
                            page_entry["latex_candidates"].append({
                                "source": "word",
                                "block_index": bidx,
                                "line_index": lidx,
                                "word_index": widx,
                                "text": wtext,
                                "bbox": wbbox,
                                "crop_image": crop_path,
                                "latex": None
                            })

        # 2) fallback: if no candidates found from OCR geometry, do image-based detection
        if not page_entry["latex_candidates"]:
            img_candidates = detect_formula_by_image(page_img_path)
            for idx, bbox in enumerate(img_candidates):
                crop_path = str(OUT_DIR / f"page_{i}_imgcandidate_{idx}.png")
                crop_and_save(page_img_path, bbox, crop_path)
                page_entry["latex_candidates"].append({
                    "source": "image_detect",
                    "bbox": bbox,
                    "crop_image": crop_path,
                    "latex": None
                })

        # 3) try to run formula model on each crop (if model available)
        for cand in page_entry["latex_candidates"]:
            crop_img = cand["crop_image"]
            if PIX2TEX_AVAILABLE and pix2tex_model:
                try:
                    # pix2tex CLI callable expects PIL Image or path depending on version
                    # we try both safely
                    try:
                        latex_out = pix2tex_model(Image.open(crop_img))
                    except Exception:
                        latex_out = pix2tex_model(crop_img)
                    cand["latex"] = latex_out.strip() if latex_out else None
                    cand["latex_model"] = "pix2tex"
                except Exception as e:
                    cand.setdefault("errors", []).append(f"pix2tex_err:{e}")
            elif RAPID_AVAILABLE and rapid_model:
                try:
                    with open(crop_img, "rb") as f:
                        b = f.read()
                    res = rapid_model(b)  # rapid returns (latex, elapsed) or similar
                    if isinstance(res, tuple):
                        cand["latex"] = res[0]
                    else:
                        cand["latex"] = res
                    cand["latex_model"] = "rapid-latex"
                except Exception as e:
                    cand.setdefault("errors", []).append(f"rapid_err:{e}")
            else:
                # model not available -> leave crop for manual checking
                cand["latex_model"] = None

        report["pages"].append(page_entry)

    # Save JSON report
    with open("latex_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pdf_to_latex_map.py input.pdf")
        sys.exit(1)
    pdf_path = sys.argv[1]
    r = asyncio.run(process_pdf(pdf_path))
    print("Saved latex_report.json. Summary:")
    for p in r["pages"]:
        print(f"Page {p['page_index']}: {len(p['latex_candidates'])} latex candidates (cropped images in {OUT_DIR})")
