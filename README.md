# Instagram Downloader

## Project Overview

Build a production-ready Django web application that downloads Instagram Reels, Photos, Videos, and Carousel Posts from public Instagram URLs.

---

# Tech Stack

* Python 3.12+
* Django 5+
* Bootstrap 5
* HTML5
* CSS3
* JavaScript
* yt-dlp

---

# Core Features

## Feature 1: Instagram URL Input

User can paste:

* https://www.instagram.com/reel/*
* https://www.instagram.com/p/*
* https://www.instagram.com/tv/*

Validate URL before processing.

---

## Feature 2: Metadata Extraction

Extract:

* Title
* Thumbnail
* Upload Date
* Duration
* Resolution
* Media Type

---

## Feature 3: Download Support

Supported Media:

### Reel

Download MP4 video

### Photo

Download JPG image

### Carousel

Download all media separately

---

# UI Requirements

Single Page Application

Sections:

1. Header
2. URL Input
3. Loading State
4. Results Area
5. Download Buttons
6. Footer

Use Bootstrap 5.

Must be mobile responsive.

---

# Project Structure

instagram_downloader/

├── manage.py
├── requirements.txt
├── README.md
├── downloader/
│   ├── views.py
│   ├── services.py
│   ├── urls.py
│   ├── forms.py
│   └── utils.py
├── templates/
├── static/
└── media/

---

# Backend Requirements

Create service layer.

Functions:

* validate_instagram_url()
* extract_metadata()
* download_media()
* cleanup_old_files()

Business logic must never be placed directly inside views.

---

# Security Requirements

Allow only:

* instagram.com
* [www.instagram.com](http://www.instagram.com)

Prevent:

* Path traversal
* Arbitrary file download
* Invalid URLs

Sanitize filenames.

---

# Error Handling

Handle:

* Invalid URL
* Private Account
* Login Required
* Deleted Post
* Timeout
* Network Errors

Show friendly messages.

---

# Performance

Use ThreadPoolExecutor.

Downloads should not block request processing.

---

# File Cleanup

Delete files older than 30 minutes.

Implement cleanup service.

---

# Logging

Configure application logging.

Log:

* Request received
* Download started
* Download completed
* Error events

---

# Code Standards

Follow:

* PEP8
* Type Hints
* Docstrings
* Django Best Practices
* Service Layer Architecture

---

# Deliverables

Generate:

* Complete Django project
* requirements.txt
* settings.py
* urls.py
* views.py
* services.py
* forms.py
* HTML
* CSS
* JavaScript

All code must be production ready and executable immediately.

---

# Author

* **Hardik Jethava**

