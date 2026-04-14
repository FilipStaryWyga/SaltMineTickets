"""
Bot rezerwacji biletow - GR8WAY
Premium Edition v3 — Resizable · Mercedes E-class · Live Log
"""

import time
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import math
import random
import os
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    root = tk.Tk(); root.withdraw()
    messagebox.showerror("Brak bibliotek", "Zainstaluj:\npip install selenium webdriver-manager")
    sys.exit(1)

# ── PALETA ─────────────────────────────────────────────────────────────────────
BG_VOID      = "#080C14"
BG_CARD      = "#0D1420"
BG_PANEL     = "#111927"
BG_INPUT     = "#0A1220"
BORDER_DIM   = "#1E2D45"
BORDER_GLOW  = "#2A4060"
GOLD         = "#C8A84B"
GOLD_BRIGHT  = "#E8C870"
GOLD_DIM     = "#6B5520"
TEXT_PRIMARY = "#E8EDF5"
TEXT_MUTED   = "#5A7090"
TEXT_DIM     = "#2E4060"
STATUS_OK    = "#2ECC71"
STATUS_WARN  = "#F39C12"
STATUS_ERR   = "#E74C3C"
STATUS_INFO  = "#5BA3D9"

DOMYSLNY_URL = "https://bilety.kopalnia.pl/rezerwacja/nienumerowane.html"

driver     = None
bot_aktywny = False


def blend(hex_col, alpha, bg=(8, 12, 20)):
    r = int(hex_col[1:3], 16); g = int(hex_col[3:5], 16); b = int(hex_col[5:7], 16)
    return (f"#{int(r*alpha+bg[0]*(1-alpha)):02X}"
            f"{int(g*alpha+bg[1]*(1-alpha)):02X}"
            f"{int(b*alpha+bg[2]*(1-alpha)):02X}")


# ── MERCEDES E-KLASSE ANIMOWANY PASEK ─────────────────────────────────────────
class MercedesStrip(tk.Canvas):
    """
    Pasek statusu z prawdziwym zdjęciem Mercedesa E-klasy jadącego po nocnej
    drodze. Tło renderowane przez PIL (alpha compositing), auto nakładane
    przez create_image z PhotoImage.
    """

    # Ścieżka do zdjęcia — szukamy obok skryptu lub w uploads
    _CAR_PATHS = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "mercedes.png"),
        "/mnt/user-data/uploads/mercedes.png",
    ]

    def __init__(self, parent, height=120, **kw):
        super().__init__(parent, height=height, bg=BG_VOID,
                         highlightthickness=0, **kw)
        self.h             = height
        self.car_x         = -320.0
        self.speed         = 8.7
        self.t             = 0.0
        self._status_color = TEXT_DIM
        self._status_text  = "Status: Gotowy"
        self._timer_text   = ""
        self._tk_img       = None   # referencja PhotoImage (bez GC)
        self._pil_car      = None   # oryginał RGBA
        self._car_w        = 0
        self._car_h        = 0
        self.stars = [{"x": random.uniform(0, 800),
                       "y": random.uniform(2, 32),
                       "s": random.uniform(0.5, 1.8),
                       "ph": random.uniform(0, 6.28)} for _ in range(55)]
        self._load_car()
        self._animate()

    # ── ładowanie zdjęcia ────────────────────────────────────────────────────
    def _load_car(self):
        try:
            from PIL import Image as PilImage
            for path in self._CAR_PATHS:
                if os.path.exists(path):
                    src = PilImage.open(path).convert("RGBA")
                    # Skaluj: wysokość = 88% paska (reszta = droga + bufor)
                    target_h = int(self.h * 0.4)
                    ratio    = target_h / src.height
                    target_w = int(src.width * ratio)
                    self._pil_car = src.resize((target_w, target_h),
                                              PilImage.LANCZOS)
                    self._car_w, self._car_h = target_w, target_h
                    return
        except Exception:
            pass
        # Fallback — brak obrazu (narysujemy nic)
        self._pil_car = None

    # ── status settery ───────────────────────────────────────────────────────
    def set_status(self, text, color=TEXT_DIM):
        self._status_text  = text
        self._status_color = color

    def set_timer(self, text):
        self._timer_text = text

    # ── konwersja hex → tuple RGB ────────────────────────────────────────────
    @staticmethod
    def _hex_to_rgb(h):
        return (int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))

    # ── główna pętla animacji ────────────────────────────────────────────────
    def _animate(self):
        self.delete("all")
        self.t += 0.04
        w = self.winfo_width() or 560
        h = self.h

        # — niebo (gradient ciemny → granat) ——————————————————————————————
        bands = 18
        sky_h = int(h * 0.76)
        for i in range(bands):
            frac = i / bands
            r2 = int(0x08 + int(0x06 * frac))
            g2 = int(0x0C + int(0x0C * frac))
            b2 = int(0x14 + int(0x1C * frac))
            y0 = int(sky_h * i / bands)
            y1 = int(sky_h * (i + 1) / bands) + 1
            self.create_rectangle(0, y0, w, y1,
                                  fill=f"#{r2:02X}{g2:02X}{b2:02X}", outline="")

        # — gwiazdy ————————————————————————————————————————————————————————
        for s in self.stars:
            pulse = 0.5 + 0.5 * math.sin(self.t * 1.1 + s["ph"])
            col   = blend("#C8D8F0", 0.10 + 0.40 * pulse)
            ss    = s["s"]
            self.create_oval(s["x"] - ss, s["y"] - ss,
                             s["x"] + ss, s["y"] + ss,
                             fill=col, outline="")
            s["x"] -= 0.28
            if s["x"] < 0:
                s["x"] = w + 2
                s["y"] = random.uniform(2, sky_h * 0.55)

        gy = sky_h   # linia gruntu

        # — droga ——————————————————————————————————————————————————————————
        self.create_rectangle(0, gy, w, h, fill="#090C14", outline="")
        # blask asfaltu pod autem (miękki reflektor)
        bx_beam = int(self.car_x) + self._car_w // 2
        beam_w  = 220
        self.create_oval(bx_beam - beam_w, gy + 2,
                         bx_beam + beam_w, gy + 28,
                         fill=blend(GOLD, 0.06), outline="")
        # złota krawędź jezdni
        self.create_line(0, gy, w, gy, fill=blend(GOLD, 0.20), width=1)
        # przerywana linia środkowa
        dash_y  = gy + int((h - gy) * 0.55)
        period  = 52
        offset  = int(self.t * 0) % period
        x = -offset
        while x < w + period:
            self.create_rectangle(x, dash_y - 1, x + 28, dash_y + 1,
                                  fill=blend(GOLD_DIM, 0.50), outline="")
            x += period
        # pobocze
        self.create_rectangle(0, gy + 1, w, gy + 6,
                              fill=blend("#081020", 0.9), outline="")

        # — Mercedes (obraz PIL composited) ————————————————————————————————
        self.car_x += self.speed
        if self.car_x > w + self._car_w + 20:
            self.car_x = -float(self._car_w + 20)

        if self._pil_car is not None:
            ## gy to linia horyzontu (początek drogi)
            # self._car_h to wysokość Twojego auta
            # Odejmujemy wysokość, ale dodajemy mały margines (np. 15-20 pikseli), 
            # aby auto "zeszło" z nieba na asfalt.

            car_y = gy - self._car_h + 20  # Zwiększaj tę liczbę (np. +25, +30), żeby auto było niżej
            ix    = int(self.car_x)
            iy    = int(car_y)

            # Przycinamy do widzialnego obszaru
            x1_src = max(0, -ix)
            x2_src = min(self._car_w, w - ix)
            if x2_src > x1_src:
                crop   = self._pil_car.crop((x1_src, 0, x2_src, self._car_h))
                # Konwersja do PhotoImage — tkinter obsłuży RGBA przez PPM hack
                from PIL import ImageTk
                self._tk_img = ImageTk.PhotoImage(crop)
                dest_x = max(0, ix)
                dest_y = iy
                self.create_image(dest_x, dest_y,
                                  image=self._tk_img, anchor="nw")

            # wiązka reflektora (prawa strona auta = przód)
            headlight_x = ix + self._car_w
            headlight_y = gy - 18
            beam_pts = [
                headlight_x,      headlight_y,
                headlight_x + 260, gy - 4,
                headlight_x + 260, gy,
                headlight_x,      gy - 8,
            ]
            self.create_polygon(beam_pts,
                                fill=blend("#FFFEF0", 0.045), outline="")

        # — status overlay ——————————————————————————————————————————————————
        dx, dy = 14, 10
        pulse  = 0.5 + 0.5 * math.sin(self.t * 2.8)
        rr     = 7 + 3 * pulse
        rc     = blend(self._status_color, 0.22 * (1 - pulse))
        self.create_oval(dx - rr, dy - rr, dx + rr, dy + rr,
                         outline=rc, width=2)
        self.create_oval(dx - 5, dy - 5, dx + 5, dy + 5,
                         fill=self._status_color, outline="")
        self.create_text(dx + 18, dy, text=self._status_text,
                         fill=self._status_color,
                         font=("Segoe UI", 9, "bold"), anchor="w")

        # — timer (prawy górny róg) ————————————————————————————————————————
        if self._timer_text:
            self.create_text(w - 12, dy, text=self._timer_text,
                             fill=GOLD_BRIGHT,
                             font=("Segoe UI", 9, "bold"), anchor="e")

        # złota linia górna
        self.create_line(0, 0, w, 0, fill=blend(GOLD, 0.25), width=1)

        self.after(20, self._animate)


# ── PULSING DOT ────────────────────────────────────────────────────────────────
class PulsingDot(tk.Canvas):
    def __init__(self, parent, color=STATUS_OK, size=10, **kw):
        super().__init__(parent, width=size*4, height=size,
                         bg=BG_CARD, highlightthickness=0, **kw)
        self.color = color; self.size = size; self.t = 0
        self._animate()

    def set_color(self, c): self.color = c

    def _animate(self):
        self.delete("all")
        self.t += 0.12
        p  = 0.5 + 0.5*math.sin(self.t)
        s  = self.size
        cx = s*0.5 + 2; cy = s*0.5
        rr = s*0.5*(1 + 0.6*p)
        self.create_oval(cx-rr, cy-rr, cx+rr, cy+rr,
                         outline=blend(self.color, 0.25*(1-p)), width=2)
        self.create_oval(cx-s*0.35, cy-s*0.35, cx+s*0.35, cy+s*0.35,
                         fill=self.color, outline="")
        self.after(40, self._animate)


# ── PREMIUM BUTTON ─────────────────────────────────────────────────────────────
class PremiumButton(tk.Canvas):
    def __init__(self, parent, text, command=None, style="primary", width=160, **kw):
        h = 40
        super().__init__(parent, width=width, height=h,
                         highlightthickness=0, cursor="hand2", **kw)
        self.command = command; self.text = text; self.style = style
        self.w = width; self.h = h
        self.hover = False; self.shimmer_x = -width; self._enabled = True
        self._draw()
        self.bind("<Enter>",           self._on_enter)
        self.bind("<Leave>",           self._on_leave)
        self.bind("<Button-1>",        self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._shimmer_loop()

    def _rrect(self, x1, y1, x2, y2, r, **kw):
        self.create_polygon(
            x1+r,y1, x2-r,y1, x2,y1+r, x2,y2-r,
            x2-r,y2, x1+r,y2, x1,y2-r, x1,y1+r,
            smooth=True, **kw)

    def _draw(self, pressed=False):
        self.delete("all")
        w, h = self.w, self.h
        ox = 2 if pressed else 0; oy = 2 if pressed else 0
        self.configure(bg=BG_CARD)
        if not self._enabled:
            self._rrect(ox, oy, w-ox, h-oy, 6,
                        fill=BG_PANEL, outline=BORDER_DIM, width=1)
            self.create_text(w//2, h//2, text=self.text,
                             fill=TEXT_DIM, font=("Segoe UI", 9, "bold"))
            return
        if self.style == "primary":
            bg = GOLD_BRIGHT if self.hover else GOLD
            fg = BG_VOID; border = GOLD_BRIGHT
        else:
            bg = BG_PANEL if self.hover else BG_INPUT
            fg = TEXT_PRIMARY if self.hover else TEXT_MUTED
            border = BORDER_GLOW if self.hover else BORDER_DIM
        self._rrect(ox, oy, w-ox, h-oy, 6, fill=bg, outline=border, width=1)
        if self.style == "primary" and self.hover:
            sx = self.shimmer_x
            if 0 < sx < w:
                self.create_line(sx, oy, sx-18, h-oy, fill="#FFFFFF44", width=10)
        self.create_text(w//2, h//2, text=self.text,
                         fill=fg, font=("Segoe UI", 9, "bold"))

    def _on_enter(self, e):
        if self._enabled: self.hover = True;  self._draw()
    def _on_leave(self, e):
        if self._enabled: self.hover = False; self._draw()
    def _on_click(self, e):
        if self._enabled: self._draw(pressed=True)
    def _on_release(self, e):
        if self._enabled:
            self._draw()
            if self.command: self.command()

    def _shimmer_loop(self):
        if self.hover and self.style == "primary" and self._enabled:
            self.shimmer_x += 9
            if self.shimmer_x > self.w + 40: self.shimmer_x = -40
            self._draw()
        self.after(28, self._shimmer_loop)

    def config_state(self, state):
        self._enabled = (state == "normal")
        self.hover = False
        self._draw()
        self.configure(cursor="hand2" if self._enabled else "arrow")


# ── GOLD SPINBOX ───────────────────────────────────────────────────────────────
class GoldSpinbox(tk.Frame):
    def __init__(self, parent, from_=0, to=99, initial=0, **kw):
        super().__init__(parent, bg=BG_CARD, **kw)
        self.val = tk.IntVar(value=initial)
        self.from_ = from_; self.to = to
        bkw = dict(bg=BG_PANEL, fg=GOLD, font=("Segoe UI", 12, "bold"),
                   relief="flat", width=2, cursor="hand2",
                   activebackground=BORDER_GLOW, activeforeground=GOLD_BRIGHT,
                   borderwidth=0)
        tk.Button(self, text="−", command=self._dec, **bkw).pack(side="left")
        tk.Label(self, textvariable=self.val, width=4, bg=BG_INPUT,
                 fg=TEXT_PRIMARY, font=("Segoe UI", 11, "bold"),
                 relief="flat").pack(side="left", padx=2)
        tk.Button(self, text="+", command=self._inc, **bkw).pack(side="left")

    def _inc(self):
        if self.val.get() < self.to:    self.val.set(self.val.get() + 1)
    def _dec(self):
        if self.val.get() > self.from_: self.val.set(self.val.get() - 1)
    def get(self): return str(self.val.get())


# ── LOG BOX ────────────────────────────────────────────────────────────────────
class LogBox(tk.Canvas):
    COLOR_MAP  = {"INFO": TEXT_MUTED, "OK": STATUS_OK,
                  "WARN": STATUS_WARN, "ERR": STATUS_ERR, "LIMIT": STATUS_WARN}
    PREFIX_MAP = {"INFO": " ●", "OK": " ✓", "WARN": " ⚡",
                  "ERR": " ✕", "LIMIT": " ⚠"}

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_VOID, highlightthickness=0, **kw)
        self.lines  = []
        self.font   = ("Consolas", 8)
        self.line_h = 17
        self.pad    = 10
        self.bind("<Configure>", self._redraw)

    def add_line(self, msg, typ="INFO"):
        col = self.COLOR_MAP.get(typ, TEXT_MUTED)
        pre = self.PREFIX_MAP.get(typ, " ?")
        ts  = datetime.now().strftime("%H:%M:%S")
        self.lines.append((f"{pre}  {ts}  {msg}", col))
        if len(self.lines) > 300: self.lines = self.lines[-300:]
        self._redraw()

    def _redraw(self, *_):
        self.delete("all")
        w = self.winfo_width()  or 480
        h = self.winfo_height() or 120
        vis   = max(1, (h - self.pad*2) // self.line_h)
        shown = self.lines[-vis:]
        for i, (txt, col) in enumerate(shown):
            self.create_text(self.pad, self.pad + i*self.line_h,
                             text=txt, fill=col, font=self.font, anchor="nw")


# ── BOT LOGIC ──────────────────────────────────────────────────────────────────
def log_gui(msg, typ="INFO", widget=None):
    if widget: widget.add_line(msg, typ)

def dodaj_bilety_turbo(drv, config, log):
    log("Próba namierzenia biletów...", "INFO")
    rodzaje = [("normalny", ["normalny", "normal", "standard"])]
    try:
        WebDriverWait(drv, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "tr")))
    except:
        log("Nie doczekano się na załadowanie tabeli.", "ERR")
        return False
    wiersze    = drv.find_elements(By.CSS_SELECTOR, "tr")
    znaleziono = False
    for klucz, slowa in rodzaje:
        ilosc = config["bilety"].get(klucz, 0)
        if ilosc <= 0: continue
        for wiersz in wiersze:
            html = wiersz.get_attribute("innerHTML").lower()
            if any(s.lower() in html for s in slowa):
                try:
                    plus_btn = None
                    for b in wiersz.find_elements(By.TAG_NAME, "button"):
                        if "+" in b.text or "plus" in b.get_attribute("class").lower():
                            plus_btn = b; break
                    if plus_btn:
                        log(f"Dodaję {ilosc}x {klucz}...", "OK")
                        drv.execute_script(
                            "var b=arguments[0],n=arguments[1];"
                            "for(var i=0;i<n;i++){b.click();}",
                            plus_btn, ilosc)
                        znaleziono = True
                        time.sleep(0.3); break
                except: continue
    return znaleziono

def dodaj_do_koszyka_turbo(drv, log):
    log("Szukam przycisku finalizacji...", "INFO")
    return drv.execute_script("""
        var btns=document.querySelectorAll(
            'button,input[type="submit"],a,.btn,.button,.btn-next');
        var keys=['koszyk','cart','dodaj','add','dalej','next',
                  'potwierdz','zamawiam','rezerwuj'];
        for(var b of btns){
            var t=(b.innerText||b.value||b.textContent||"").toLowerCase();
            if(keys.some(k=>t.includes(k))){
                b.scrollIntoView({block:"center"});b.click();return true;
            }
        }return false;""")

def jeden_cykl(drv, config, log, proba):
    log(f"== START CYKLU #{proba} ==", "INFO")
    drv.get(config["url"])
    if dodaj_bilety_turbo(drv, config, log):
        time.sleep(0.8)
        if dodaj_do_koszyka_turbo(drv, log):
            log("Bilety w koszyku! Sukces.", "OK")
            return True
    return False

def uruchom_bota(config, log_widget, btn_start, btn_stop, mercedes, root):
    global driver, bot_aktywny

    def log(msg, typ="INFO"):
        root.after(0, lambda m=msg, t=typ: log_gui(m, t, log_widget))
    def set_status(txt, col):
        root.after(0, lambda: mercedes.set_status(txt, col))
    def set_timer(txt):
        root.after(0, lambda: mercedes.set_timer(txt))

    bot_aktywny = True
    proba = 1

    while bot_aktywny:
        driver = None
        try:
            log(f"Uruchamiam przeglądarkę (cykl #{proba})...", "INFO")
            set_status(f"Cykl #{proba} — uruchamianie...", STATUS_WARN)
            opcje = Options()
            opcje.add_argument("--window-size=1300,1000")
            service = Service(ChromeDriverManager().install())
            driver  = webdriver.Chrome(service=service, options=opcje)
            wynik   = jeden_cykl(driver, config, log, proba)
            if wynik:
                set_status(f"✓ Sukces! Cykl #{proba} — bilety dodane", STATUS_OK)
            else:
                set_status(f"Cykl #{proba} — oczekiwanie na bilety", STATUS_INFO)

            pozostalo = 15 * 60 + 5
            while bot_aktywny and pozostalo > 0:
                time.sleep(1)
                pozostalo -= 1
                m, s = pozostalo // 60, pozostalo % 60
                set_timer(f"Odświeżenie za  {m:02d}:{s:02d}")

        except Exception as e:
            log(f"Błąd: {str(e)[:100]}", "ERR")
            set_status("Błąd — restart za chwilę", STATUS_ERR)
        finally:
            if driver:
                try: driver.quit(); log("Przeglądarka zamknięta.", "INFO")
                except: pass

        if bot_aktywny:
            proba += 1
            log("Zaraz otwieram nowy cykl...", "INFO")
            time.sleep(2)

    root.after(0, lambda: btn_start.config_state("normal"))
    root.after(0, lambda: btn_stop.config_state("normal"))
    root.after(0, lambda: mercedes.set_status("Status: Gotowy", TEXT_DIM))
    root.after(0, lambda: mercedes.set_timer(""))


# ── GUI ────────────────────────────────────────────────────────────────────────
def zbuduj_gui():
    root = tk.Tk()
    root.title("GR8WAY — Automat Biletowy")
    root.minsize(460, 620)
    root.geometry("560x760")
    root.resizable(True, True)
    root.configure(bg=BG_VOID)

    # ── tło z cząsteczkami (canvas pod wszystkim) ──
    bg_anim = tk.Canvas(root, bg=BG_VOID, highlightthickness=0)
    bg_anim.place(relx=0, rely=0, relwidth=1, relheight=1)
    particles = [{"x": random.uniform(0,600), "y": random.uniform(0,800),
                  "vx": random.uniform(-0.2,0.2), "vy": random.uniform(-0.14,-0.06),
                  "r": random.uniform(1,2.2), "alpha": random.uniform(0.1,0.4),
                  "ph": random.uniform(0,6.28)} for _ in range(20)]

    def bg_animate():
        bg_anim.delete("all")
        t  = time.time()
        cw = bg_anim.winfo_width()  or 560
        ch = bg_anim.winfo_height() or 760
        for i in range(0, cw+1, 70):
            bg_anim.create_line(i,0,i,ch, fill=blend(GOLD,0.04), width=0.5)
        for j in range(0, ch+1, 70):
            bg_anim.create_line(0,j,cw,j, fill=blend(GOLD,0.025), width=0.5)
        for p in particles:
            pulse = 0.5 + 0.5*math.sin(t*0.8 + p["ph"])
            col   = blend(GOLD_BRIGHT, p["alpha"]*(0.6+0.4*pulse))
            r     = p["r"]
            bg_anim.create_oval(p["x"]-r, p["y"]-r, p["x"]+r, p["y"]+r,
                                fill=col, outline="")
            p["x"] += p["vx"]; p["y"] += p["vy"]
            if p["y"] < -5:   p["y"] = ch+2
            if p["x"] < -5:   p["x"] = cw+2
            if p["x"] > cw+5: p["x"] = -2
        bg_anim.after(45, bg_animate)
    bg_animate()

    # ── outer frame (pack, rozciągliwy) ──
    outer = tk.Frame(root, bg=BG_VOID)
    outer.pack(fill="both", expand=True)

    # ── HEADER ──
    hdr = tk.Frame(outer, bg=BG_VOID)
    hdr.pack(fill="x", padx=24, pady=(20, 0))
    logo_row = tk.Frame(hdr, bg=BG_VOID)
    logo_row.pack()
    tk.Label(logo_row, text="GR8", bg=BG_VOID, fg=GOLD_BRIGHT,
             font=("Segoe UI", 26, "bold")).pack(side="left")
    tk.Label(logo_row, text="WAY", bg=BG_VOID, fg=TEXT_PRIMARY,
             font=("Segoe UI", 26, "bold")).pack(side="left")
    tk.Label(outer, text="TICKET AUTOMATION SYSTEM",
             bg=BG_VOID, fg=TEXT_DIM,
             font=("Segoe UI", 7, "bold")).pack()

    # separator
    sep = tk.Canvas(outer, height=14, bg=BG_VOID, highlightthickness=0)
    sep.pack(fill="x", padx=24, pady=10)
    def draw_sep(e=None):
        sep.delete("all")
        ww = sep.winfo_width() or 500
        mid = ww // 2
        sep.create_line(0, 7, mid-36, 7, fill=BORDER_DIM)
        sep.create_line(mid+36, 7, ww, 7, fill=BORDER_DIM)
        sep.create_oval(mid-4,3, mid+4,11, fill=GOLD, outline="")
        sep.create_oval(mid-18,4, mid-10,10, fill=GOLD_DIM, outline="")
        sep.create_oval(mid+10,4, mid+18,10, fill=GOLD_DIM, outline="")
        sep.create_oval(mid-30,5, mid-24,9, fill=BORDER_DIM, outline="")
        sep.create_oval(mid+24,5, mid+30,9, fill=BORDER_DIM, outline="")
    sep.bind("<Configure>", draw_sep)
    root.after(120, draw_sep)

    # ── KARTA URL ──
    card_url = tk.Frame(outer, bg=BG_CARD, padx=16, pady=10,
                        highlightbackground=BORDER_DIM, highlightthickness=1)
    card_url.pack(fill="x", padx=24, pady=(0,6))
    tk.Label(card_url, text="LINK DO REZERWACJI", bg=BG_CARD, fg=GOLD,
             font=("Segoe UI", 7, "bold")).pack(anchor="w")
    tk.Label(card_url, text="Wklej link po wybraniu języka i godziny",
             bg=BG_CARD, fg=TEXT_DIM, font=("Segoe UI", 7)).pack(anchor="w", pady=(0,4))
    url_frm = tk.Frame(card_url, bg=BG_INPUT,
                       highlightbackground=BORDER_DIM, highlightthickness=1)
    url_frm.pack(fill="x")
    e_url = tk.Text(url_frm, height=3, font=("Segoe UI", 8),
                    bg=BG_INPUT, fg=TEXT_PRIMARY, relief="flat",
                    padx=8, pady=6, insertbackground=GOLD,
                    selectbackground=GOLD_DIM, wrap="word")
    e_url.insert("1.0", DOMYSLNY_URL)
    e_url.pack(fill="x")
    e_url.bind("<FocusIn>",  lambda e: url_frm.config(highlightbackground=GOLD))
    e_url.bind("<FocusOut>", lambda e: url_frm.config(highlightbackground=BORDER_DIM))

    # ── KARTA BILETÓW ──
    card_t = tk.Frame(outer, bg=BG_CARD, padx=16, pady=10,
                      highlightbackground=BORDER_DIM, highlightthickness=1)
    card_t.pack(fill="x", padx=24, pady=(0,6))
    tk.Label(card_t, text="KONFIGURACJA BILETÓW", bg=BG_CARD, fg=GOLD,
             font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(0,6))
    pola = {}
    for klucz, opis in [("normalny", "Bilet Normalny")]:
        row = tk.Frame(card_t, bg=BG_CARD)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=opis, bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Segoe UI", 9)).pack(side="left")
        sp = GoldSpinbox(row, from_=0, to=99, initial=20)
        sp.pack(side="right")
        pola[klucz] = sp

    # ── MERCEDES STRIP ──
    mercedes = MercedesStrip(outer, height=120)
    mercedes.pack(fill="x", padx=0, pady=(2,0))

    # ── PRZYCISKI ──
    btn_frame = tk.Frame(outer, bg=BG_VOID)
    btn_frame.pack(pady=8)

    def start():
        config = {"url": e_url.get("1.0", tk.END).strip(),
                  "bilety": {k: int(v.get()) for k, v in pola.items()}}
        btn_start.config_state("disabled")
        mercedes.set_status("Uruchamianie...", STATUS_WARN)
        threading.Thread(
            target=uruchom_bota,
            args=(config, log_box, btn_start, btn_stop, mercedes, root),
            daemon=True).start()

    def stop():
        global bot_aktywny
        bot_aktywny = False
        mercedes.set_status("Zatrzymywanie...", STATUS_WARN)
        mercedes.set_timer("")

    btn_start = PremiumButton(btn_frame, "▶  URUCHOM", command=start,
                              style="primary", width=170, bg=BG_CARD)
    btn_start.pack(side="left", padx=8)
    btn_stop  = PremiumButton(btn_frame, "■  STOP", command=stop,
                              style="secondary", width=130, bg=BG_CARD)
    btn_stop.pack(side="left", padx=8)

    # ── LOG ──
    log_hdr = tk.Frame(outer, bg=BG_VOID)
    log_hdr.pack(fill="x", padx=24, pady=(2,2))
    tk.Label(log_hdr, text="DZIENNIK ZDARZEŃ", bg=BG_VOID, fg=GOLD,
             font=("Segoe UI", 7, "bold")).pack(side="left")

    log_outer = tk.Frame(outer, bg=BG_VOID,
                         highlightbackground=BORDER_DIM, highlightthickness=1)
    log_outer.pack(fill="both", expand=True, padx=24, pady=(0,16))

    log_box = LogBox(log_outer)
    log_box.pack(fill="both", expand=True)

    def intro():
        log_gui("GR8WAY Ticket Automation System zainicjalizowany.", "INFO", log_box)
        log_gui("Gotowy do pracy — wprowadź URL i kliknij URUCHOM.", "OK", log_box)
    root.after(700, intro)

    root.mainloop()


if __name__ == "__main__":
    zbuduj_gui()
