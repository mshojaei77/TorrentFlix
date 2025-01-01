from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re
import json
import os
import signal
import sys
import time
from multiprocessing import Pool, cpu_count
from functools import partial
import concurrent.futures

def signal_handler(sig, frame):
    print("\nStopping gracefully...")
    sys.exit(0)

def extract_movie_name(link):
    # Extract movie name between /review/ and the next /
    match = re.search(r'/review/([^/]+)/', link)
    if match:
        # Replace hyphens with spaces and capitalize words
        movie_name = match.group(1).replace('-', ' ').title()
        return movie_name
    return None

def get_ranker_urls_async(url_queue):
    """Continuously discover URLs and add them to the queue"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            page.goto("https://www.ranker.com/list-of/film")
            discovered_urls = set()
            
            while True:
                page.evaluate('window.scrollBy(0, 500)')
                time.sleep(1)
                
                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                list_links = soup.find_all('a', href=re.compile(r'/(list|crowdranked-list)/'))
                
                for link in list_links:
                    href = link['href']
                    if href.startswith('/'):
                        full_url = f"https://www.ranker.com{href}"
                        if full_url not in discovered_urls:
                            discovered_urls.add(full_url)
                            url_queue.put(full_url)
                            print(f"Discovered new URL: {full_url}")
                
                # Periodically save discovered URLs
                with open('lists/ranker_urls.json', 'w', encoding='utf-8') as f:
                    json.dump(list(discovered_urls), f, indent=4)
                
    except Exception as e:
        print(f"URL discovery error: {str(e)}")
    finally:
        # Signal that URL discovery is complete
        url_queue.put(None)

def scraper_worker(url_queue, max_concurrent=3):
    """Worker process that continuously pulls URLs from queue and scrapes them"""
    while True:
        try:
            url = url_queue.get()
            if url is None:  # Poison pill
                break
                
            output_file = f'lists/{url.split("/")[-2]}.json'
            scrape_ranker_movies(url, output_file)
            
        except Exception as e:
            print(f"Scraper worker error: {str(e)}")

def scrape_ranker_movies(url, output_file):
    # Set up ctrl+c handler
    signal.signal(signal.SIGINT, signal_handler)

    # Create lists directory if it doesn't exist
    if not os.path.exists('lists'):
        os.makedirs('lists')

    printed_movies = set()
    start_time = time.time()
    
    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # Go to URL
            page.goto(url)
            
            while True:
                # Check if 2 minutes have elapsed
                if time.time() - start_time > 120:  # 120 seconds = 2 minutes
                    print(f"Time limit reached for {url}")
                    break
                    
                # Scroll down continuously
                page.evaluate('window.scrollBy(0, 500)')
                time.sleep(1)  # Wait for content to load
                
                # Get current content and parse
                content = page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Find all links matching the review pattern
                review_links = soup.find_all('a', href=re.compile(r'/review/[^/]+/\d+'))
                
                # Process new movies and write to file
                new_movies = []
                for link in review_links:
                    movie_name = extract_movie_name(link['href'])
                    if movie_name and movie_name not in printed_movies:
                        new_movies.append(movie_name)
                        printed_movies.add(movie_name)
                        print(f"Found new movie: {movie_name}")
                
                if new_movies:
                    # Read existing movies
                    existing_movies = []
                    if os.path.exists(output_file):
                        with open(output_file, 'r', encoding='utf-8') as f:
                            existing_movies = json.load(f)
                    
                    # Combine and write all movies
                    all_movies = existing_movies + new_movies
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(all_movies, f, indent=4)
                
    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")

def run_parallel_scraping():
    """Main function to coordinate parallel URL discovery and scraping"""
    if not os.path.exists('lists'):
        os.makedirs('lists')

    # Create a queue for URL communication
    from multiprocessing import Queue, Process
    url_queue = Queue()

    # Start URL discovery process
    url_discoverer = Process(target=get_ranker_urls_async, args=(url_queue,))
    url_discoverer.start()

    # Start multiple scraper processes
    num_scrapers = max(cpu_count() // 2, 1)  # Use half of CPU cores
    scraper_processes = []
    for _ in range(num_scrapers):
        p = Process(target=scraper_worker, args=(url_queue,))
        p.start()
        scraper_processes.append(p)

    # Wait for URL discovery to complete
    url_discoverer.join()

    # Send termination signal to all scrapers
    for _ in range(num_scrapers):
        url_queue.put(None)

    # Wait for all scrapers to complete
    for p in scraper_processes:
        p.join()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    run_parallel_scraping()
