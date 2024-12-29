import os
import subprocess
import requests
import json
from urllib.parse import quote_plus

def search_jackett(query, jackett_url, api_key):
    """Search for torrents using Jackett"""
    search_url = f"{jackett_url}/api/v2.0/indexers/all/results?apikey={api_key}&Query={quote_plus(query)}"
    
    try:
        response = requests.get(search_url)
        if response.status_code != 200:
            print(f"Error searching Jackett: HTTP {response.status_code}")
            return []
            
        try:
            results = response.json()
            return results.get('Results', [])
        except json.JSONDecodeError as e:
            print(f"Error parsing Jackett response: {e}")
            print(f"Response text: {response.text[:200]}")  # Print first 200 chars of response
            return []
            
    except Exception as e:
        print(f"Error searching Jackett: {e}")
        return []

def get_magnet_link(result):
    """Extract magnet link from Jackett result"""
    return result.get('MagnetUri', '')

def stream_torrent(magnet_link, player='mpv', keep_files=False):
    """Stream torrent using btfs and media player"""
    
    # Create mount directory
    mount_dir = "/tmp/btfs_mount"
    os.makedirs(mount_dir, exist_ok=True)
    
    try:
        # Mount torrent with btfs
        subprocess.run(['btfs', magnet_link, mount_dir], check=True)
        
        # Find video file
        video_files = []
        for root, dirs, files in os.walk(mount_dir):
            for file in files:
                if file.endswith(('.mp4', '.mkv', '.avi')):
                    video_files.append(os.path.join(root, file))
        
        if video_files:
            # Play first video file found
            subprocess.run([player, video_files[0]], check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Error streaming torrent: {e}")
    finally:
        # Cleanup
        subprocess.run(['fusermount', '-u', mount_dir], check=True)
        if not keep_files:
            os.rmdir(mount_dir)

def main(query, player='mpv', keep_files=False):
    # Load config
    config = {}
    config_file = os.path.expanduser('~/.config/btstrm.conf')
    if os.path.exists(config_file):
        with open(config_file) as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=')
                    config[key.strip()] = value.strip()
    
    jackett_url = config.get('JACKETT_URL', 'http://127.0.0.1:9117')
    api_key = config.get('JACKETT_API_KEY', '')
    
    # Validate configuration
    if not api_key:
        print("Error: Jackett API key not configured. Please add JACKETT_API_KEY to ~/.config/btstrm.conf")
        return
    
    # Verify Jackett is accessible
    try:
        requests.get(jackett_url)
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to Jackett at {jackett_url}")
        print("Please ensure:")
        print("1. Jackett is running")
        print("2. The JACKETT_URL in ~/.config/btstrm.conf is correct")
        return
    
    # Search for torrents
    results = search_jackett(query, jackett_url, api_key)
    
    if results:
        # Get first result's magnet link
        magnet = get_magnet_link(results[0])
        if magnet:
            stream_torrent(magnet, player, keep_files)
        else:
            print("No magnet link found")
    else:
        print("No torrents found")

if __name__ == "__main__":
    # Example usage:
    # Search and stream a movie using default player (mpv)
    main("Pulp Fiction")
    
    # Search and stream using VLC player
    # main("Pulp Fiction", player="vlc")
    
    # Stream and keep downloaded files
    # main("Matrix", keep_files=True)
