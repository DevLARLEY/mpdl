<img src="https://github.com/DevLARLEY/mpdl/blob/main/icon.png?raw=true" alt="drawing" width="200"/>

# === Please do not use this anymore it's a terrbile piece of software ===

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
1. Select a CDM
2. If not already in your PATH, select an ffmpeg and mp4decrypt executable
3. Optionally, specify a download directory in the settings (default is the program's root)
4. Hit 'Apply'
5. Start the Browser
+ If you just want to download:
6. Open the URL Sniffer
7. Navigate to a Website utilizing DRM
8. Choose "License URLs" in the drop-down menu
9. Select a License URL from the list and hit 'Select'
10. Choose "MPD URLs" from the drop-down menu
11. Select an MPD URL from the list and hit 'Download'
+ If you want more control:
6. Open the advanced mode.
7. Enter everything you have. (**use the internal browser if you want to have the request headers automatically transferred to pywidevine**)
8. Hit 'Download'

![image](https://github.com/DevLARLEY/mpdl/assets/121249322/f51cf92c-cbc6-438e-a562-5b9500fed4d8)
