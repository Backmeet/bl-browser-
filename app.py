from flask import Flask, request, Response, send_file
from typing import Tuple, Union, List
from bs4 import BeautifulSoup
from PIL import Image
import requests
import hashlib
import re
import io
import math

app = Flask(__name__)

# Global state
SIZE = 32
currentURL = "https://discord.gg"
last_hash = None
button_links: List[Union[str, None]] = []
image_links: List[Union[str, None]] = []

# small encoding table retained
encodeing = {
    " ": "00000000", "a": "00000001", "b": "00000010", "c": "00000011",
    "d": "00000100", "e": "00000101", "f": "00000110", "g": "00000111",
    "h": "00001000", "i": "00001001", "j": "00001010", "k": "00001011",
    "l": "00001100", "m": "00001101", "n": "00001110", "o": "00001111",
    "p": "00010000", "q": "00010001", "r": "00010010", "s": "00010011",
    "t": "00010100", "u": "00010101", "v": "00010110", "w": "00010111",
    "x": "00011000", "y": "00011001", "z": "00011010", "1": "00011011",
    "2": "00011100", "3": "00011101", "4": "00011110", "5": "00011111",
    "6": "00100000", "7": "00100001", "8": "00100010", "9": "00100011",
    "0": "00100100", "-": "00100101", "=": "00100110", ".": "00100111",
    ",": "00101000", ";": "00101001", "/": "00101010", "à": "00101011",
    "â": "00101100", "ç": "00101101", "è": "00101110", "é": "00101111",
    "ê": "00110000", "î": "00110001", "ï": "00110010", "û": "00110011",
    "|": "00110100", "[": "00110101", "]": "00110110", "\"": "00110111",
    "🟧": "00111000", "🟨": "00111001", "🟩": "00111010", "🟦": "00111011",
    "🟪": "00111100", "⬜": "00111101", "▶": "00111110", "": "00111111",
    "A": "01000001", "B": "01000010", "C": "01000011", "D": "01000100",
    "E": "01000101", "F": "01000110", "G": "01000111", "H": "01001000",
    "I": "01001001", "J": "01001010", "K": "01001011", "L": "01001100",
    "M": "01001101", "N": "01001110", "O": "01001111", "P": "01010000",
    "Q": "01010001", "R": "01010010", "S": "01010011", "T": "01010100",
    "U": "01010101", "V": "01010110", "W": "01010111", "X": "01011000",
    "Y": "01011001", "Z": "01011010", "!": "01011011", "@": "01011100",
    "#": "01011101", "$": "01011110", "%": "01011111", "?": "01100000",
    "&": "01100001", "*": "01100010", "(": "01100011", ")": "01100100",
    "_": "01100101", "+": "01100110", ".": "01100111", "'": "01101000",
    ":": "01101001", "~": "01101010", "À": "01101011", "Â": "01101100",
    "Ç": "01101101", "È": "01101110", "É": "01101111", "Ê": "01110000",
    "Ì": "01110001", "Ï": "01110010", "Û": "01110011", "¦": "01110100",
    "{": "01110101", "}": "01110110", "^": "01110111", ">": "01111000",
    "<": "01111001", "█": "01111010", "➡": "01111011", "⬅": "01111100",
    "⬆": "01111101", "⬇": "01111110", "\n": "00000000", "":"00000000"
}

class pixel:
    def __init__(self, colour: Tuple[int, int, int], chr: str):
        self.colour = colour
        self.chr = chr

    def getBin(self):
        return (
            encodeing.get(self.chr, "00000000"),
            # pack coarse 2-bit per channel into 6 bits
            "00" + format(self.colour[0] // 64, "02b") +
            format(self.colour[1] // 64, "02b") +
            format(self.colour[2] // 64, "02b")
        )

screen: List[List[pixel]] = [[pixel((0, 0, 0), " ") for _ in range(SIZE)] for _ in range(SIZE)]

def setPixel(x, y, bg=None, chr=None):
    if 0 <= (y % SIZE) < SIZE and 0 <= (x % SIZE) < SIZE:
        if bg is not None:
            screen[y % SIZE][x % SIZE].colour = bg
        if chr is not None:
            screen[y % SIZE][x % SIZE].chr = chr

def blitText(text, x, y, bg):
    # place text horizontally starting at x,y
    for i, letter in enumerate(text):
        setPixel(x + i, y, bg, letter)

def StableHash(text: str, filename: str = ""):
    data = f"{filename}\n{text}".encode('utf-8')
    return hashlib.sha512(data).hexdigest()

def extract_onclick_url(onclick_str: str) -> Union[str, None]:
    if not onclick_str:
        return None
    # basic patterns for common location assignments
    for pattern in [
        r"(?:location|window)\.href\s*=\s*['\"]([^'\"]+)['\"]",
        r"document\.location\s*=\s*['\"]([^'\"]+)['\"]",
        r"location\.assign\(['\"]([^'\"]+)['\"]\)",
        r"window\.open\(['\"]([^'\"]+)['\"]"
    ]:
        match = re.search(pattern, onclick_str)
        if match:
            return match.group(1)
    return None

def parse_color(style_val: str):
    if not style_val:
        return None
    # simple handler: look for background-color: #rrggbb or rgb(...)
    # return (r,g,b) tuple or None
    style_val = style_val.replace(" ", "")
    m = re.search(r"background-color:([^;]+);?", style_val, flags=re.IGNORECASE)
    if m:
        val = m.group(1)
        if val.startswith("#") and len(val) == 7:
            try:
                return tuple(int(val[i:i+2], 16) for i in (1, 3, 5))
            except:
                return None
        m2 = re.match(r"rgb\((\d+),(\d+),(\d+)\)", val, flags=re.IGNORECASE)
        if m2:
            try:
                return (int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
            except:
                return None
    return None

def shorten_url(url: str, max_len=30):
    if not url:
        return ""
    url = url.strip()
    if len(url) > max_len:
        return url[:max_len-3] + "..."
    return url

def is_valid_navigable_url(url: str):
    if not url:
        return False
    url = url.strip()
    low = url.lower()
    # filter out javascript: and mailto and fragment-only and long ones with many query params
    if low.startswith("javascript:") or low.startswith("mailto:") or low.startswith("tel:"):
        return False
    if url.startswith("#"):
        return False
    # extremely long query strings are likely noisy
    if len(url) > 200:
        return False
    return True

#
# DOM color filling helpers
#
def fill_section_color(x_start, y_start, x_end, y_end, color):
    # clamp and fill integer rectangle
    xs = max(0, int(x_start))
    ys = max(0, int(y_start))
    xe = min(SIZE, int(x_end))
    ye = min(SIZE, int(y_end))
    for yy in range(ys, ye):
        for xx in range(xs, xe):
            setPixel(xx, yy, bg=color)

def walk_and_color(tag, x=0, y=0, width=SIZE, height=SIZE, depth=0):
    """
    Recursively fill background colors based on DOM structure.
    This is a heuristic: we proportionally divide the vertical space among block children.
    """
    try:
        children = [c for c in tag.children if getattr(c, "name", None)]
    except Exception:
        children = []
    # get color from inline style or bgcolor attribute
    col = None
    if getattr(tag, "attrs", None):
        if 'style' in tag.attrs:
            col = parse_color(tag.attrs.get('style', ''))
        if not col and 'bgcolor' in tag.attrs:
            try:
                hexcol = tag.attrs['bgcolor'].strip()
                if hexcol.startswith("#") and len(hexcol) == 7:
                    col = tuple(int(hexcol[i:i+2], 16) for i in (1, 3, 5))
            except:
                pass

    if col:
        fill_section_color(x, y, x + width, y + height, col)

    if not children:
        return

    # simple layout: vertical stacking of child_count blocks
    child_count = len(children)
    child_height = max(1, height // child_count)
    cy = y
    for child in children:
        walk_and_color(child, x, cy, width, child_height, depth + 1)
        cy += child_height

#
# Rendering and element placement
#
def place_image_on_screen(img: Image.Image, top_x, top_y):
    """
    Place a PIL image (small) into the screen, mapping each image pixel to a screen cell.
    We expect img to be small (<=8x8 typically).
    """
    w, h = img.size
    img = img.convert("RGB")
    for yy in range(h):
        for xx in range(w):
            px = img.getpixel((xx, yy))
            # use a blank char for images
            setPixel(top_x + xx, top_y + yy, bg=px, chr=" ")

def find_next_free_slot_for_block(block_w, block_h, start_x=0, start_y=0):
    """Find a location where a block of size block_w x block_h fits in the grid.
       naive scan row-major. Returns (x,y) or None"""
    for y in range(start_y, SIZE - block_h + 1):
        for x in range(start_x, SIZE - block_w + 1):
            # check if all positions are default background? We'll not check occupancy; just place sequentially
            return x, y
    return None

@app.route("/Re-render")
def reRender():
    global screen, currentURL, last_hash, button_links, image_links

    try:
        r = requests.get(currentURL, timeout=6)
        html = r.text
    except Exception as e:
        return {"value": 500, "error": f"fetch failed: {e}"}

    current_hash = StableHash(html, currentURL)
    if last_hash == current_hash:
        return "Unchanged"
    # update hash
    last_hash = current_hash

    # reset state
    screen = [[pixel((0, 0, 0), " ") for _ in range(SIZE)] for _ in range(SIZE)]
    button_links = []
    image_links = []

    soup = BeautifulSoup(html, "html5lib")

    # ---------- base/background fill ----------
    bg_color = (255, 255, 255)
    body = soup.find("body")
    if body and 'style' in body.attrs:
        col = parse_color(body.attrs['style'])
        if col:
            bg_color = col
    for y in range(SIZE):
        for x in range(SIZE):
            setPixel(x, y, bg=bg_color)

    # recursively fill colored sections (heuristic)
    walk_and_color(body or soup, 0, 0, SIZE, SIZE)

    # ---------- element extraction ----------
    # We'll keep two element lists:
    # - elements: list of (type, label, href, bg_color_for_label)
    # types: "button", "link", "image"
    elements = []
    used = 0

    # helper to resolve absolute url if needed
    def resolve_href(base, href):
        if not href:
            return None
        href = href.strip()
        if href.startswith("//"):
            # protocol-relative
            if base.startswith("https:"):
                return "https:" + href
            elif base.startswith("http:"):
                return "http:" + href
            else:
                return "https:" + href
        if href.startswith("http://") or href.startswith("https://"):
            return href
        # relative URL
        try:
            from urllib.parse import urljoin
            return urljoin(base, href)
        except:
            return href

    for tag in soup.find_all(["a", "button", "img"]):
        if used >= 255:
            break

        if tag.name == "a":
            raw_href = tag.get("href", "") or ""
            href = resolve_href(currentURL, raw_href)
            if not is_valid_navigable_url(href):
                continue
            text = tag.get("title") or tag.get_text(strip=True) or raw_href or "Link"
            label = f"(B:{text[:20]}:{used})"
            # try to get button-like bg color for link if present
            bcol = None
            if 'style' in tag.attrs:
                bcol = parse_color(tag.attrs['style'])
            elements.append(("link", label, href, bcol))
            button_links.append(href)
            used += 1

        elif tag.name == "button":
            # extract possible onclick target first
            raw_onclick = tag.get("onclick", "") or ""
            href = extract_onclick_url(raw_onclick)
            if not href:
                raw_href = tag.get("href", "") or ""
                href = resolve_href(currentURL, raw_href)
            if not is_valid_navigable_url(href):
                # still allow button with no href if it has text - but don't set link
                href = None
            text = tag.get("title") or tag.get_text(strip=True) or "Button"
            # detect button background color from style
            bcol = None
            if 'style' in tag.attrs:
                bcol = parse_color(tag.attrs['style'])
            # fallback: some buttons use class names; we won't parse CSS files here
            label = f"(B:{text[:20]}:{used})"
            elements.append(("button", label, resolve_href(currentURL, href) if href else None, bcol))
            button_links.append(resolve_href(currentURL, href) if href else None)
            used += 1

        elif tag.name == "img":
            raw_src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src") or ""
            src = resolve_href(currentURL, raw_src)
            if not src:
                continue
            # alt/title
            alt = tag.get("alt") or tag.get("title") or "Image"
            label = f"(IMG:{alt[:12]}:{used})"
            # store for image route
            image_links.append(src)
            elements.append(("image", label, src, None))
            button_links.append(src)  # clicking the ID will open the src (as requested)
            used += 1

    # ---------- element placement on the 32x32 grid ----------
    # two cursors: one for small inline labels (buttons/links), one for images (we keep them grouped)
    cursor_x = 0
    cursor_y = 0

    # first, place images because they occupy a block (8x8) and label under them
    for idx, elem in enumerate(elements):
        typ, label, href, bcol = elem
        if typ != "image":
            continue
        if len(image_links) <= 0:
            continue
        img_id = image_links.index(href) if href in image_links else None
        # fetch image and create a small thumbnail (8x8) but preserve aspect ratio
        try:
            resp = requests.get(href, timeout=4)
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            # decide thumbnail size within 8x8 while preserving aspect
            w, h = img.size
            ratio = min(8 / max(1, w), 8 / max(1, h))
            tw = max(1, int(round(w * ratio)))
            th = max(1, int(round(h * ratio)))
            img_small = img.resize((tw, th), Image.LANCZOS)
        except Exception:
            # fallback empty block
            img_small = Image.new("RGB", (8, 8), (200, 200, 200))
            tw, th = img_small.size
            img_id = img_id if img_id is not None else idx

        # find placement
        if cursor_x + 8 > SIZE:
            cursor_x = 0
            cursor_y += 9  # 8 for image + 1 for label
        if cursor_y + 9 > SIZE:
            # no space left; skip rendering images if no room
            continue

        # center the small image in an 8x8 box for nicer look
        off_x = (8 - tw) // 2
        off_y = (8 - th) // 2
        place_image_on_screen(Image.new("RGB", (8, 8), (0, 0, 0)), cursor_x, cursor_y)  # ensure block exists
        # copy pixels of img_small into the box at (cursor_x+off_x, cursor_y+off_y)
        for yy in range(th):
            for xx in range(tw):
                px = img_small.getpixel((xx, yy))
                setPixel(cursor_x + off_x + xx, cursor_y + off_y + yy, bg=px, chr=" ")

        # label under the image (one row)
        lab = label[:SIZE - cursor_x]  # clip label length
        blitText(lab, cursor_x, cursor_y + 8, bg=(255, 255, 255))
        cursor_x += 9  # move to next block horizontally

    # after images, place buttons/links as labels left-to-right, top-to-bottom
    # start at top-left again or after images end
    # To avoid overwriting images we can start placing labels at row 0 and allow overwriting (labels are text on top)
    lab_x = 0
    lab_y = 0
    for idx, elem in enumerate(elements):
        typ, label, href, bcol = elem
        if typ == "image":
            continue
        # clip label so it fits
        lab = label[:SIZE]  # never exceed row width
        lab_len = len(lab)
        # if not enough horizontal space, wrap to next line
        if lab_x + lab_len > SIZE:
            lab_x = 0
            lab_y += 1
        if lab_y >= SIZE:
            break

        # if button with background color - fill area with that color for realism
        if typ == "button" and bcol:
            fill_section_color(lab_x, lab_y, lab_x + lab_len, lab_y + 1, bcol)
            blitText(lab, lab_x, lab_y, bg=bcol)
        else:
            # for links, if they have bcol we already set; else render with page bg (we'll use existing pixel bg)
            # choose label bg as the underlying pixel bg for contrast (use the screen pixel bg color)
            underlying = screen[lab_y][lab_x].colour if 0 <= lab_y < SIZE and 0 <= lab_x < SIZE else (255,255,255)
            blitText(lab, lab_x, lab_y, bg=underlying)

        # ensure button_links list lines up with index: we already appended hrefs earlier in the same order
        lab_x += lab_len + 1  # 1 cell gap

    # end render
    return {"value": 200, "elements": len(elements)}

@app.route("/image/<int:img_id>")
def render_image(img_id):
    """
    Fetch the original image, resize to 32x32, and return PNG bytes.
    """
    if 0 <= img_id < len(image_links):
        img_url = image_links[img_id]
        try:
            resp = requests.get(img_url, timeout=6)
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            img.thumbnail((32, 32), Image.LANCZOS)
            # ensure exact size 32x32 by pasting onto transparent background if needed
            out = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            ox = (32 - img.width) // 2
            oy = (32 - img.height) // 2
            out.paste(img, (ox, oy), img if img.mode == "RGBA" else None)
            buf = io.BytesIO()
            out.save(buf, format="PNG")
            buf.seek(0)
            return send_file(buf, mimetype="image/png")
        except Exception as e:
            return {"value": 500, "error": f"image fetch/render failed: {e}"}
    return {"value": 404}

@app.route("/colour", methods=["GET"])
def sendColour():
    # expects r_x, r_y to exist
    try:
        return {"value": screen[r_y][r_x].getBin()[1]}
    except Exception:
        return {"value": "err"}

@app.route("/text", methods=["GET"])
def sendChr():
    try:
        return {"value": screen[r_y][r_x].getBin()[0]}
    except Exception:
        return {"value": "err"}

# cursor for read endpoints
r_x = 0
r_y = 0

@app.route("/x", methods=["POST"])
def set_r_x():
    global r_x
    r_x = int(request.form["value"], 2)
    return {"value":200}

@app.route("/y", methods=["POST"])
def set_r_y():
    global r_y
    r_y = int(request.form["value"], 2)
    return {"value":200}

@app.route("/click", methods=["POST"])
def click():
    """
    POST 'value' is binary index string representing which element ID was clicked.
    We assume button_links list order matches the labels created during render.
    """
    global currentURL
    try:
        index = int(request.form.get("value", "0"), 2)
    except:
        return {"value":300}
    if 0 <= index < len(button_links):
        target = button_links[index]
        if target:
            currentURL = target
            return {"value":201}
    return {"value":300}

if __name__ == "__main__":
    app.run(port=8080)
