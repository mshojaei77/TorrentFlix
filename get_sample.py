import requests

url = "https://www.rottentomatoes.com/m/inception"
response = requests.get(url)

with open("sample.html", "w", encoding="utf-8") as f:
    f.write(response.text)