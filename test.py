import requests

url = "https://torrentgalaxy.to/torrents.php?search=silo#results"
response = requests.get(url)

with open("sample.html", "w", encoding="utf-8") as f:
    f.write(response.text)