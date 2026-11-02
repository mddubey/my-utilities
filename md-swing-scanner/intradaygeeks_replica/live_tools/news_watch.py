import re, sys, time, html, datetime as dt, urllib.request, urllib.parse, xml.etree.ElementTree as ET
# Polls a few RSS feeds for war / oil / Hormuz headlines. Feed content is untrusted text: only titles are printed.
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
Q = "(Iran OR Hormuz OR Houthi OR \"Israel strike\" OR tanker OR \"oil facility\" OR Netanyahu OR Aramco OR Ukraine OR \"Russia refinery\" OR Taiwan OR \"North Korea\" OR Pakistan OR sanctions) when:2h"
FEEDS = {
    "GoogleNews": "https://news.google.com/rss/search?q=" + urllib.parse.quote(Q) + "&hl=en-US&gl=US&ceid=US:en",
    "BBC": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml",
    "AlJazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "Guardian": "https://www.theguardian.com/world/iran/rss",
}
KEY = re.compile(r"\b(iran|irgc|hormuz|houthi|tanker|israel|netanyahu|strike|missile|mine[sd]?|refiner|oil|ras tanura|aramco|ceasefire|attack|ukrain|russia|taiwan|china|korea|pakistan|sanction|drone|refinery)\w*", re.I)
_E = re.compile(r"\b(hormuz|tanker|aramco|ras tanura|abqaiq|(saudi|gulf|iran\w*|kuwait\w*|emirat\w*|qatar\w*) (refiner\w*|oil)|oil (field|facilit|termin)|energy (facilit|infrastruct)|iran)\w*", re.I)
_V = re.compile(r"\b(attack|strike|struck|fire|ablaze|explod|mine[sd]?|seiz|close[sd]?|closure|hit|missile|drone|blast|sink|sank)\w*", re.I)
_W = re.compile(r"\b(prices?|monthly|weekly|set for|rates?|futures|stocks|markets?|analysis|explainer|why|how)\b", re.I)  # market wraps / analysis -> hourly batch
class _Strong:  # instant alert only for an EVENT at energy assets (asset word AND action word), not analysis pieces
    def search(self, t): return _E.search(t) and _V.search(t) and not _W.search(t)
STRONG = _Strong()
seen, pending, last_emit = set(), [], time.time()
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read()
first = True
while True:
    now = dt.datetime.now(IST)
    if dt.time(8, 30) <= now.time() < dt.time(9, 0): break
    for src, url in FEEDS.items():
        try:
            root = ET.fromstring(fetch(url))
            for it in root.iter("item"):
                t = html.unescape((it.findtext("title") or "").strip())
                k = re.sub(r"\W+", " ", t.lower())[:90]
                if not t or k in seen: continue
                seen.add(k)
                if first or not KEY.search(t): continue
                pending.append((("!! " if STRONG.search(t) else "") + f"[{src}] {t[:180]}", bool(STRONG.search(t))))
        except Exception as e:
            print(f"ERR {now:%H:%M} {src} {type(e).__name__}", flush=True)
    first = False
    strong = [p for p, s in pending if s]
    if strong:   # energy / Hormuz headlines go out immediately
        print(f"NEWS-HOT {now:%H:%M} " + " || ".join(strong[:4]), flush=True)
        pending = [x for x in pending if not x[1]]
    if pending and time.time() - last_emit >= 3600:   # everything else batched every 60 min
        last_emit = time.time()
        print(f"NEWS {now:%H:%M} ({len(pending)} new) " + " || ".join(p for p, _ in pending[:6]), flush=True)
        pending = []
    time.sleep(180)
print("END news watch stopped at 08:30", flush=True)
