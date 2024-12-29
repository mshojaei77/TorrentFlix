import subprocess
import os

url = 'https://yts.mx/torrent/download/D55F1E840F1BD6576EAD67A4D04E5D6EA294414B'

try:
    # Use Free Download Manager CLI to download the torrent file
    fdm_path = r"C:\Program Files\Softdeluxe\Free Download Manager\fdm.exe"
    
    if not os.path.exists(fdm_path):
        print("Free Download Manager not found. Please install it first.")
    else:
        subprocess.run([fdm_path, url, "--saveto", "movie.torrent"], check=True)
        print("Torrent file download started in Free Download Manager")

except subprocess.CalledProcessError as e:
    print(f"Error launching Free Download Manager: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
