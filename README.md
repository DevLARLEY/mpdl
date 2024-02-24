<img src="https://github.com/DevLARLEY/mpdl/blob/main/icon.png?raw=true" alt="drawing" width="200"/>

# === ONLY TESTED ON WINDOWS FOR NOW ===

# mpdl
GUI-Based MPD Downloader for DRM Protected content.

# Requirements
+ Python 3.12
+ ffmpeg
+ mp4decrypt
+ [**Content Decryption Module**](https://forum.videohelp.com/threads/408031-Dumping-Your-own-L3-CDM-with-Android-Studio)
+ Firefox (Installed)

# Setup
+ Clone the Repo
+ Install the required modules: `pip3 install -r requirements.txt`
+ Run mpdl: `python3 mpdl.py`

# Usage
+ Select a CDM
+ If not already in your PATH, select an ffmpeg and mp4decrypt executable
+ Optionally, specify a download directory in the settings (default is the program's root)
+ Hit 'Apply'
+ Start the Browser
+ Open the URL Sniffer
+ Navigate to a Website utilizing DRM
+ Choose "License URLs" in the drop-down menu
+ Select a License URL from the list and hit 'Select'
+ Choose "MPD URLs" from the drop-down menu
+ Select an MPD URL from the list and hit 'Download'


![image](https://github.com/DevLARLEY/mpdl/assets/121249322/f51cf92c-cbc6-438e-a562-5b9500fed4d8)
