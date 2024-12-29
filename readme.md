# TorrentFlix

![TorrentFlix Logo](app.png)

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Architecture](#architecture)
  - [Core Components](#core-components)
  - [Class Structure](#class-structure)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Dependencies](#dependencies)
  - [Environment Setup](#environment-setup)
- [Usage](#usage)
  - [Running the Application](#running-the-application)
  - [Application Workflow](#application-workflow)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Customizing Sources](#customizing-sources)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Troubleshooting](#troubleshooting)

## Introduction

**TorrentFlix** is a sophisticated desktop application designed to streamline the process of searching for and downloading torrents of your favorite movies and TV shows. By leveraging multiple torrent sources and integrating comprehensive metadata from renowned platforms like **TMDB**, **IMDB**, and **Metacritic**, TorrentFlix ensures a seamless and enriched experience for users seeking detailed information and high-quality media content.

## Features

- **Multi-Source Torrent Search**: Aggregates torrents from various platforms such as YTS, 1337x, RARBG, and more, ensuring a wide range of options.
- **Comprehensive Metadata Integration**: Fetches detailed metadata including ratings, genres, cast, and summaries from TMDB, IMDB, and Metacritic for an enriched viewing experience.
- **User-Friendly GUI**: Built with PyQt, the intuitive interface offers a customizable title bar, easy navigation through search history, and a responsive design.
- **Efficient Caching Mechanism**: Optimizes performance by caching data, reducing redundant API calls, and ensuring faster load times.
- **Concurrent Operations**: Utilizes multi-threading to handle torrent searching and metadata retrieval concurrently, enhancing efficiency.

## Architecture

TorrentFlix is structured to ensure modularity, scalability, and maintainability. Below is an overview of its core architecture and components.

### Core Components

1. **User Interface (UI)**
   - Built with **PyQt5**, providing a sleek and responsive GUI.
   - Handles user interactions, displays search results, and manages torrent downloads.

2. **Torrent Search Module**
   - Interfaces with multiple torrent sources.
   - Handles the aggregation and filtering of torrent data based on user queries.

3. **Metadata Integration**
   - Fetches and processes metadata from **TMDB**, **IMDB**, and **Metacritic**.
   - Enhances the user experience by providing detailed information about movies and TV shows.

4. **Downloading Mechanism**
   - Integrates with **Free Download Manager (FDM)** for efficient torrent downloading.
   - Manages download processes and logs download statistics.

5. **Caching System**
   - Implements caching strategies to store frequently accessed data.
   - Reduces the number of API calls, enhancing performance and reducing latency.

### Class Structure

TorrentFlix employs a clean and organized class structure to manage its functionalities. The primary classes include:

- **MovieSearchApp**: Manages the main application window and user interactions.
- **PosterDownloader**: Handles downloading of movie posters.
- **MovieSelectionDialog**: Provides a dialog for selecting movies from search results.
- **TorrentSearcher**: Manages the search and retrieval of torrents from various sources.

## Installation

To get TorrentFlix up and running on your local machine, follow the steps below.

### Prerequisites

Ensure that your system meets the following requirements:

- **Operating System**: Windows, macOS, or Linux.
- **Python**: Version 3.7 or higher.
- **Package Manager**: `pip` for Python package installations.

### Dependencies

TorrentFlix relies on several Python packages to function seamlessly. Install the required dependencies using the following command:

```bash
pip install -r requirements.txt
```

### Environment Setup

1. **Clone the Repository**

   ```bash
   git clone https://github.com/mshojaei77/TorrentFlix.git
   cd TorrentFlix
   ```

2. **Create a Virtual Environment (Optional but Recommended)**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**

   a. **Get TMDB API Key**
      - Visit [TMDB website](https://www.themoviedb.org/) and create a free account
      - Go to your account settings -> API section
      - Click "Request an API key"
      - Fill out the form selecting "Developer" option
      - Once approved, copy your API key (v3 auth)

   b. **Configure Environment File**
      Create a `.env` file in the project root directory and add your TMDB API key:

      ```dotenv
      TMDB_API_KEY=YOUR_TMDB_API_KEY
      ```

      Ensure that the `.env` file is added to `.gitignore` to prevent exposing sensitive information.

## Usage

### Running the Application

Navigate to the project directory and execute the following command to launch TorrentFlix:

```bash
python app.py
```

Upon successful execution, the TorrentFlix GUI will appear, allowing you to search for and download your desired torrents.

### Application Workflow

1. **Search for a Movie or TV Show**

   - Enter the title of the movie or TV show in the search bar.
   - Select your preferred torrent source from the dropdown menu.
   - Press `Enter` or click the `Search` button to initiate the search.

2. **Select Desired Content**

   - A dialog will appear displaying a list of available movies matching your search query.
   - Double-click on the desired movie to view detailed information.

3. **View Details and Download**

   - Detailed metadata, including ratings, genres, cast, and descriptions, will be displayed.
   - Browse through available torrents and select the one that best suits your needs.
   - Click the `Download` button to initiate the torrent download via Free Download Manager.

4. **Download Management**

   - Torrents are downloaded using **Free Download Manager (FDM)**.
   - Download statistics are logged for your reference.

## Configuration

### Environment Variables

TorrentFlix utilizes environment variables to manage API keys and other configurations securely.

- **TMDB_API_KEY**: API key for The Movie Database (TMDB) to fetch movie metadata.

### Customizing Sources

TorrentFlix supports multiple torrent sources categorized for ease of use. You can customize or add new sources by modifying the `torrent_search.py` module.

**Adding a New Torrent Source**:

1. Open `torrent_search.py`.
2. Define the new source within the `TorrentSource` class, specifying its configuration.
3. Ensure that the source is categorized appropriately for easy selection within the UI.

## Contributing

Contributions to TorrentFlix are highly appreciated! Follow the steps below to contribute to the project:

1. **Fork the Repository**

   Click the `Fork` button at the top right of the repository page to create your own copy.

2. **Clone Your Fork**

   ```bash
   git clone https://github.com/mshojaei77/TorrentFlix.git
   cd TorrentFlix
   ```

3. **Create a New Branch**

   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Make Your Changes**

   Implement your feature or bug fix. Ensure that your code adheres to the project's coding standards and includes necessary documentation.

5. **Commit Your Changes**

   ```bash
   git commit -m "Add feature: your-feature-name"
   ```

6. **Push to Your Fork**

   ```bash
   git push origin feature/your-feature-name
   ```

7. **Submit a Pull Request**

   Navigate to the original repository and click the `New Pull Request` button. Provide a clear description of your changes and submit the request.

## License

TorrentFlix is licensed under the [MIT License](LICENSE), granting users significant freedom to use, modify, and distribute the software. Please refer to the [LICENSE](LICENSE) file for detailed information.

## Acknowledgments

- **Built with Python and PyQt**: Leveraging the power of Python for backend processing and PyQt for a responsive and intuitive user interface.
- **Metadata Providers**: Metadata integration courtesy of TMDB, IMDB, and Metacritic, ensuring comprehensive and accurate information.
- **Free Download Manager (FDM)**: Utilizing FDM for efficient torrent downloading and management.

## Troubleshooting

If you encounter issues while using TorrentFlix, consider the following solutions:

1. **Application Doesn't Launch**

   - Ensure that all dependencies are installed correctly.
   - Verify that you are using Python 3.7 or higher.
   - Check for any error messages in the terminal and address them accordingly.

2. **Cannot Connect to Torrent Sources**

   - Verify your internet connection.
   - Ensure that your VPN is enabled if accessing torrent sources is restricted in your region.
   - Check if the torrent sources are operational or experiencing downtime.

3. **Metadata Not Displaying Correctly**

   - Ensure that your TMDB API key is correctly set in the `.env` file.
   - Verify that the API key has the necessary permissions and quotas.

4. **Download Issues with Free Download Manager**

   - Confirm that Free Download Manager (FDM) is installed at the path specified in `app.py`.
   - Ensure that FDM is updated to the latest version.
   - Check if FDM is running properly by attempting a manual download.

5. **UI Glitches or Responsiveness Issues**

   - Ensure that your system meets the required specifications.
   - Try restarting the application.
   - If issues persist, consider reinstalling the application to reset configurations.

For further assistance, feel free to open an [issue](https://github.com/mshojaei77/TorrentFlix/issues) on the repository.

---

*Happy Streaming with TorrentFlix!*