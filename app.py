from flask import Flask, request
from typing import Tuple, Union, List
from bs4 import BeautifulSoup
import PIL
import requests
import hashlib
import re

app = Flask(__name__)

# Global state
SIZE = 32
currentURL = "https://google.com"
last_hash = None
button_links: List[Union[str, None]] = []

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
    def __init__(self, colour: Tuple[int], chr: str):
        self.colour = colour
        self.chr = chr

    def getBin(self):
        return (
            encodeing.get(self.chr, "00000000"),
            "00" + format(self.colour[0] // 64, "02b") +
            format(self.colour[1] // 64, "02b") +
            format(self.colour[2] // 64, "02b")
        )

screen: List[List[pixel]] = [[pixel((0, 0, 0), " ") for _ in range(SIZE)] for _ in range(SIZE)]

def setPixel(x, y, bg=None, chr=None):
    if bg:
        screen[y % SIZE][x % SIZE].colour = bg
    if chr:
        screen[y % SIZE][x % SIZE].chr = chr

def blitText(text, x, y, bg):
    for i, letter in enumerate(text):
        setPixel(x + i, y, bg, letter)

def StableHash(text: str, filename: str = ""):
    data = f"{filename}\n{text}".encode('utf-8')
    return hashlib.sha512(data).hexdigest()

def extract_onclick_url(onclick_str: str) -> Union[str, None]:
    # location.href or window.href or document.location
    for pattern in [
        r"(?:location|window)\.href\s*=\s*['\"]([^'\"]+)['\"]",
        r"document\.location\s*=\s*['\"]([^'\"]+)['\"]"
    ]:
        match = re.search(pattern, onclick_str)
        if match:
            return match.group(1)
    return None

@app.route("/Re-render")
def reRender():
    global screen, currentURL, last_hash, button_links

    r = requests.get(currentURL)
    html = r.text
    current_hash = StableHash(html, currentURL)

    if last_hash == current_hash:
        return "Unchanged"

    last_hash = current_hash
    screen = [[pixel((0, 0, 0), " ") for _ in range(SIZE)] for _ in range(SIZE)]
    button_links = []

    soup = BeautifulSoup(html, "html5lib")

    # Step 1: Background color
    bg_color = (255, 255, 255)
    body = soup.find("body")
    if body and 'style' in body.attrs:
        style = body.attrs['style']
        if 'background-color' in style:
            try:
                colour = style.split("background-color:")[1].split(";")[0].strip()
                if colour.startswith("#") and len(colour) == 7:
                    bg_color = tuple(int(colour[i:i+2], 16) for i in (1, 3, 5))
            except:
                pass

    # Step 2: Fill screen with color
    for y in range(SIZE):
        for x in range(SIZE):
            setPixel(x, y, bg=bg_color)

    # Step 3: Extract elements
    buttons = []
    used = 0
    for tag in soup.find_all(["a", "button", "img"]):
        if used >= 255:
            break

        text = ""
        href = None

        if tag.name == "a":
            text = tag.get("title") or tag.get_text(strip=True) or tag.get("href") or "Link"
            href = tag.get("href")

        elif tag.name == "button":
            text = tag.get("title") or tag.get_text(strip=True) or "Button"
            href = extract_onclick_url(tag.get("onclick", ""))

        elif tag.name == "img":
            text = tag.get("alt") or tag.get("title") or "Image"
            href = tag.get("src")

        # Fallback onclick
        if not href:
            onclick = tag.get("onclick", "")
            href = extract_onclick_url(onclick)

        if not text.strip():
            continue

        label = f"(B:{text[:20]}:{used})"
        buttons.append((label, href))
        button_links.append(href)
        used += 1

    # Step 4: Overlay button labels (3 lines per column, wrap if needed)
    bx, by = 0, 0
    for label, _ in buttons:
        blitText(label, bx, by, bg_color)
        by += 1
        if by >= SIZE:
            by = 0
            bx += 10

    return {"value":200}

@app.route("/colour", methods=["GET"])
def sendColour():
    return screen[r_y][r_x].getBin()[1]

@app.route("/text", methods=["GET"])
def sendChr():
    return screen[r_y][r_x].getBin()[0]

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
    global currentURL
    index = int(request.form.get("index", -1))
    if 0 <= index < len(button_links):
        target = button_links[index]
        if target:
            currentURL = target
            return {"value":201}
    return {"value":300}
