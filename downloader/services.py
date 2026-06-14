import os
import re
import time
import shutil
import logging
import urllib.parse
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional

import yt_dlp
import requests
from django.conf import settings
from downloader.utils import sanitize_filename

logger = logging.getLogger('downloader')

# Thread pool for non-blocking file downloads
download_executor = ThreadPoolExecutor(max_workers=4)

# Thread-safe in-memory task database
DOWNLOAD_TASKS: Dict[str, Dict[str, Any]] = {}
tasks_lock = threading.Lock()

def get_proxy_config() -> Optional[str]:
    """Retrieves proxy string from environment variables."""
    return os.environ.get('INSTAGRAM_PROXY') or os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')

def get_requests_proxies() -> Optional[Dict[str, str]]:
    """Generates proxies dictionary for the requests library and instaloader."""
    proxy = get_proxy_config()
    if proxy:
        return {
            'http': proxy,
            'https': proxy
        }
    return None

def validate_instagram_url(url: str) -> bool:
    """
    Validates that a URL is a valid Instagram Reel, Post, or TV URL.
    Restricts hostnames strictly to instagram.com / www.instagram.com.
    """
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        # Check domain
        host = parsed.netloc.lower()
        if host not in ['instagram.com', 'www.instagram.com']:
            return False
        
        # Check path
        path = parsed.path
        # Normalize double slashes
        path = re.sub(r'/+', '/', path)
        
        if not (path.startswith('/reel/') or path.startswith('/p/') or path.startswith('/tv/')):
            return False
            
        if '..' in path or '\\' in path:
            return False
            
        return True
    except Exception as e:
        logger.error(f"URL validation exception for {url}: {e}")
        return False

import instaloader

def extract_metadata_instaloader(url: str) -> Dict[str, Any]:
    """Helper to extract metadata using instaloader as a fallback."""
    m = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
    if not m:
        raise ValueError("Invalid URL: Could not extract shortcode.")
    shortcode = m.group(1)
    
    L = instaloader.Instaloader()
    proxies = get_requests_proxies()
    if proxies:
        L.context.session.proxies = proxies
    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
    except Exception as e:
        logger.error(f"Instaloader metadata fallback failed for {shortcode}: {e}")
        raise ValueError("Instagram Block: Failed to fetch metadata using both yt-dlp and Instaloader.")
        
    metadata = {}
    metadata['title'] = post.caption or f"Instagram Post by {post.owner_username}"
    if len(metadata['title']) > 120:
        metadata['title'] = metadata['title'][:117] + "..."
        
    metadata['thumbnail'] = post.url
    
    if post.date_utc:
        metadata['upload_date'] = post.date_utc.strftime("%B %d, %Y")
    else:
        metadata['upload_date'] = "Unknown"
        
    if post.is_video and post.video_duration:
        mins, secs = divmod(int(post.video_duration), 60)
        metadata['duration'] = f"{mins:02d}:{secs:02d}"
    else:
        metadata['duration'] = "N/A"
        
    metadata['resolution'] = "Unknown"
    
    if post.typename == 'GraphSidecar':
        metadata['media_type'] = "Carousel"
    elif post.is_video:
        path_parsed = urllib.parse.urlparse(url).path
        if path_parsed.startswith('/reel/'):
            metadata['media_type'] = "Reel"
        else:
            metadata['media_type'] = "Video"
    else:
        metadata['media_type'] = "Photo"
        
    return metadata

def extract_metadata(url: str) -> Dict[str, Any]:
    """
    Extracts metadata from a public Instagram URL using yt-dlp.
    Falls back to Instaloader for image posts/carousels that yt-dlp fails to extract.
    """
    logger.info(f"Metadata extraction requested for URL: {url}")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    proxy = get_proxy_config()
    if proxy:
        ydl_opts['proxy'] = proxy
    
    cookies_path = os.path.join(settings.BASE_DIR, 'cookies.txt')
    if os.path.exists(cookies_path):
        ydl_opts['cookiefile'] = cookies_path
        logger.info(f"Loaded cookies file from: {cookies_path}")
        
    info = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        err_msg = str(e)
        logger.warning(f"yt-dlp extraction failed for {url}, attempting Instaloader fallback. Error: {err_msg}")
        # If it's a known non-blocking warning, or format extraction issue, fall back
        return extract_metadata_instaloader(url)
        
    # If yt-dlp extracted successfully but found 0 entries in a playlist (e.g. image carousel), fall back
    if info and info.get('_type') == 'playlist' and len(info.get('entries', [])) == 0:
        logger.info("yt-dlp returned 0 entries for playlist, falling back to Instaloader.")
        return extract_metadata_instaloader(url)
        
    # If yt-dlp returned single item but lacks media URL or formats, fall back
    if info and not info.get('url') and not info.get('formats'):
        logger.info("yt-dlp returned no downloadable url or formats, falling back to Instaloader.")
        return extract_metadata_instaloader(url)

    # Parse metadata fields from yt-dlp
    metadata = {}
    metadata['title'] = info.get('title') or info.get('description') or "Instagram Media"
    if len(metadata['title']) > 120:
        metadata['title'] = metadata['title'][:117] + "..."
        
    metadata['thumbnail'] = info.get('thumbnail') or ""
    
    upload_date_str = info.get('upload_date')
    if upload_date_str:
        try:
            dt = datetime.strptime(upload_date_str, "%Y%m%d")
            metadata['upload_date'] = dt.strftime("%B %d, %Y")
        except Exception:
            metadata['upload_date'] = upload_date_str
    else:
        metadata['upload_date'] = "Unknown"
        
    duration = info.get('duration')
    if duration:
        mins, secs = divmod(int(duration), 60)
        metadata['duration'] = f"{mins:02d}:{secs:02d}"
    else:
        metadata['duration'] = "N/A"
        
    width = info.get('width')
    height = info.get('height')
    if width and height:
        metadata['resolution'] = f"{width}x{height}"
    else:
        metadata['resolution'] = "Unknown"
        
    path_parsed = urllib.parse.urlparse(url).path
    if 'entries' in info:
        metadata['media_type'] = "Carousel"
    elif path_parsed.startswith('/reel/'):
        metadata['media_type'] = "Reel"
    elif path_parsed.startswith('/tv/'):
        metadata['media_type'] = "Video"
    else:
        vcodec = info.get('vcodec')
        if vcodec and vcodec != 'none':
            metadata['media_type'] = "Video"
        else:
            metadata['media_type'] = "Photo"
            
    return metadata

def zip_downloaded_files(task_dir: str, files: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Creates a ZIP archive containing all downloaded files for a task."""
    if len(files) <= 1:
        return None
        
    import zipfile
    zip_filename = "all_media_archive.zip"
    zip_filepath = os.path.join(task_dir, zip_filename)
    
    try:
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for f in files:
                file_path = os.path.join(task_dir, f['name'])
                if os.path.exists(file_path):
                    zip_file.write(file_path, arcname=f['name'])
                    
        size = os.path.getsize(zip_filepath)
        if size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"
            
        relative_url = f"{settings.MEDIA_URL}downloads/{os.path.basename(task_dir)}/{zip_filename}"
        return {
            'url': relative_url,
            'name': zip_filename,
            'size': size_str
        }
    except Exception as e:
        logger.error(f"Failed to create ZIP archive in {task_dir}: {e}")
        return None

def update_task_status(task_id: str, status: str, files: Optional[List[Dict[str, Any]]] = None, zip_file: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
    """Updates the thread-safe download status registry."""
    with tasks_lock:
        DOWNLOAD_TASKS[task_id] = {
            'status': status,
            'files': files or [],
            'zip_file': zip_file,
            'error': error,
            'updated_at': time.time()
        }

def download_media_instaloader(url: str, task_id: str):
    """Downloads media files using Instaloader data."""
    m = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
    if not m:
        raise ValueError("Invalid URL: Could not extract shortcode.")
    shortcode = m.group(1)
    
    L = instaloader.Instaloader()
    proxies = get_requests_proxies()
    if proxies:
        L.context.session.proxies = proxies
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    
    media_items = []
    if post.typename == 'GraphSidecar':
        # Carousel
        for idx, node in enumerate(post.get_sidecar_nodes()):
            media_url = node.video_url if node.is_video else node.display_url
            ext = 'mp4' if node.is_video else 'jpg'
            media_items.append({
                'url': media_url,
                'ext': ext,
                'name': f"media_{idx + 1}"
            })
    else:
        # Single item
        media_url = post.video_url if post.is_video else post.url
        ext = 'mp4' if post.is_video else 'jpg'
        media_items.append({
            'url': media_url,
            'ext': ext,
            'name': "media_1"
        })
        
    if not media_items:
        raise ValueError("No downloadable links found via Instaloader.")
        
    task_dir = os.path.join(settings.MEDIA_ROOT, 'downloads', task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    downloaded_files = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    for item in media_items:
        filename = sanitize_filename(f"{item['name']}.{item['ext']}")
        filepath = os.path.join(task_dir, filename)
        
        abs_filepath = os.path.abspath(filepath)
        abs_media_root = os.path.abspath(settings.MEDIA_ROOT)
        if not abs_filepath.startswith(abs_media_root):
            raise ValueError("Path traversal violation during writing.")
            
        logger.info(f"Instaloader fallback: Streaming direct link to {filepath}")
        r = requests.get(item['url'], headers=headers, stream=True, timeout=45, proxies=get_requests_proxies())
        r.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in r.iter_content(chunk_size=16384):
                if chunk:
                    f.write(chunk)
                    
        size = os.path.getsize(filepath)
        if size < 1024 * 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f} MB"
            
        relative_url = f"{settings.MEDIA_URL}downloads/{task_id}/{filename}"
        downloaded_files.append({
            'url': relative_url,
            'name': filename,
            'size': size_str
        })
        
    # Archive files in a zip if multiple
    zip_data = zip_downloaded_files(task_dir, downloaded_files)
    logger.info(f"Instaloader download worker completed successfully for Task ID: {task_id}")
    update_task_status(task_id, 'completed', files=downloaded_files, zip_file=zip_data)

def select_best_progressive_format(formats: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Selects the highest quality progressive format (containing both video and audio).
    A format is progressive if:
    1. It has a video extension (typically 'mp4').
    2. Its vcodec is not 'none' and acodec is not 'none'.
    """
    if not formats:
        return None
    
    progressive_formats = []
    for f in formats:
        ext = f.get('ext') or ''
        vcodec = f.get('vcodec')
        acodec = f.get('acodec')
        
        # Must be a video extension (typically 'mp4' on Instagram)
        if ext not in ['mp4', 'webm', 'mkv']:
            continue
            
        # Codecs must not be 'none'
        if vcodec != 'none' and acodec != 'none':
            progressive_formats.append(f)
            
    if progressive_formats:
        return progressive_formats[-1]
        
    return None

def get_format_extension(format_dict: Dict[str, Any]) -> str:
    """Gets correct extension for format dict."""
    ext = format_dict.get('ext')
    if ext:
        return ext
    vcodec = format_dict.get('vcodec')
    if vcodec and vcodec != 'none':
        return 'mp4'
    return 'jpg'

def download_media_worker(url: str, task_id: str):
    """Worker task run in the background to fetch media streams via requests."""
    logger.info(f"Download started in background for Task ID: {task_id}")
    update_task_status(task_id, 'processing')
    
    # Try running via yt-dlp first
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        proxy = get_proxy_config()
        if proxy:
            ydl_opts['proxy'] = proxy
        cookies_path = os.path.join(settings.BASE_DIR, 'cookies.txt')
        if os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        # If yt-dlp found 0 entries in a playlist (e.g. image carousel), fall back
        if info and info.get('_type') == 'playlist' and len(info.get('entries', [])) == 0:
            logger.info("yt-dlp returned 0 entries, falling back to Instaloader download worker.")
            download_media_instaloader(url, task_id)
            return
            
        # If yt-dlp lacks media url and formats, fall back
        if info and not info.get('url') and not info.get('formats'):
            logger.info("yt-dlp returned no download urls, falling back to Instaloader download worker.")
            download_media_instaloader(url, task_id)
            return

        # Collect download specifications from yt-dlp data
        media_items = []
        if 'entries' in info:
            for idx, entry in enumerate(info['entries']):
                formats = entry.get('formats', [])
                selected_format = select_best_progressive_format(formats) if formats else None
                
                if selected_format:
                    media_url = selected_format.get('url')
                    ext = get_format_extension(selected_format)
                else:
                    media_url = entry.get('url')
                    if not media_url and formats:
                        media_url = formats[-1].get('url')
                    ext = entry.get('ext') or ('mp4' if (entry.get('vcodec') and entry.get('vcodec') != 'none') else 'jpg')
                
                if media_url:
                    media_items.append({
                        'url': media_url,
                        'ext': ext,
                        'name': f"media_{idx + 1}"
                    })
        else:
            formats = info.get('formats', [])
            selected_format = select_best_progressive_format(formats) if formats else None
            
            if selected_format:
                media_url = selected_format.get('url')
                ext = get_format_extension(selected_format)
            else:
                media_url = info.get('url')
                if not media_url and formats:
                    media_url = formats[-1].get('url')
                ext = info.get('ext') or ('mp4' if (info.get('vcodec') and info.get('vcodec') != 'none') else 'jpg')
                
            if media_url:
                media_items.append({
                    'url': media_url,
                    'ext': ext,
                    'name': "media_1"
                })
                
        if not media_items:
            # Try Instaloader fallback if yt-dlp failed to find urls
            logger.warning("yt-dlp extracted successfully but failed to find files. Falling back to Instaloader.")
            download_media_instaloader(url, task_id)
            return
            
        task_dir = os.path.join(settings.MEDIA_ROOT, 'downloads', task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        downloaded_files = []
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, http_headers/120.0.0.0 Chrome/120.0.0.0 Safari/537.36',
        }
        
        for item in media_items:
            filename = sanitize_filename(f"{item['name']}.{item['ext']}")
            filepath = os.path.join(task_dir, filename)
            
            abs_filepath = os.path.abspath(filepath)
            abs_media_root = os.path.abspath(settings.MEDIA_ROOT)
            if not abs_filepath.startswith(abs_media_root):
                raise ValueError("Path traversal violation during writing.")
                
            logger.info(f"Streaming direct media link to {filepath}")
            r = requests.get(item['url'], headers=headers, stream=True, timeout=45, proxies=get_requests_proxies())
            r.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
                        
            size = os.path.getsize(filepath)
            if size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
                
            relative_url = f"{settings.MEDIA_URL}downloads/{task_id}/{filename}"
            downloaded_files.append({
                'url': relative_url,
                'name': filename,
                'size': size_str
            })
            
        # Archive files in a zip if multiple
        zip_data = zip_downloaded_files(task_dir, downloaded_files)
        logger.info(f"Download completed successfully for Task ID: {task_id}")
        update_task_status(task_id, 'completed', files=downloaded_files, zip_file=zip_data)
        
    except Exception as e:
        logger.warning(f"yt-dlp download failed, attempting Instaloader download fallback. Error: {e}")
        try:
            download_media_instaloader(url, task_id)
        except Exception as fallback_err:
            logger.error(f"Instaloader download fallback also failed for Task ID {task_id}: {fallback_err}")
            update_task_status(task_id, 'failed', error=str(fallback_err))

def download_media(url: str, task_id: str):
    """Submits the download worker to the concurrent thread pool executor."""
    download_executor.submit(download_media_worker, url, task_id)

def cleanup_old_files():
    """
    Deletes files/folders in the downloads directory that are older than 30 minutes.
    Also clears expired task tracking states in memory.
    """
    downloads_dir = os.path.join(settings.MEDIA_ROOT, 'downloads')
    if not os.path.exists(downloads_dir):
        return
        
    now = time.time()
    cutoff = now - (30 * 60)  # 30 minutes threshold
    
    # Filesystem Sweep
    for folder_name in os.listdir(downloads_dir):
        folder_path = os.path.join(downloads_dir, folder_name)
        try:
            if os.path.isdir(folder_path):
                # Check dir mtime
                if os.path.getmtime(folder_path) < cutoff:
                    shutil.rmtree(folder_path)
                    logger.info(f"Cleaned up expired download directory: {folder_path}")
            else:
                if os.path.getmtime(folder_path) < cutoff:
                    os.remove(folder_path)
                    logger.info(f"Cleaned up expired file: {folder_path}")
        except Exception as e:
            logger.error(f"Error cleaning {folder_path}: {e}")
            
    # Cache Dictionary Sweep
    with tasks_lock:
        expired_ids = [tid for tid, tdata in DOWNLOAD_TASKS.items() if tdata.get('updated_at', 0) < cutoff]
        for tid in expired_ids:
            del DOWNLOAD_TASKS[tid]
            logger.info(f"Cleaned task metadata in memory for: {tid}")
