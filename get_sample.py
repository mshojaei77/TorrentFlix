import requests
from urllib.parse import urlparse
import os

url = "https://www.ranker.com/list/best-movies-about-geniuses/ranker-film"
response = requests.get(url)

domain = urlparse(url).netloc
if not os.path.exists("samples"):
    os.makedirs("samples")

with open(f"samples/{domain}.html", "w", encoding="utf-8") as f:
    f.write(response.text)