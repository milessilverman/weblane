"""Inline Leaflet's stylesheet (the artifact host blocks external CSS) -> web/index.html."""
from pathlib import Path

here = Path(__file__).resolve().parent
src = (here / "index.src.html").read_text()
css = (here / "leaflet-1.9.4.css").read_text()
(here / "index.html").write_text(src.replace("/*LEAFLET_CSS*/", css))
print("wrote", here / "index.html")
