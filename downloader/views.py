import uuid
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import ensure_csrf_cookie

from downloader.forms import InstagramURLForm
from downloader.services import (
    extract_metadata,
    download_media,
    cleanup_old_files,
    DOWNLOAD_TASKS
)

logger = logging.getLogger('downloader')

@ensure_csrf_cookie
def index(request):
    """
    Renders the Single Page Application index page.
    Injects a CSRF cookie to protect AJAX API calls.
    """
    form = InstagramURLForm()
    return render(request, 'downloader/index.html', {'form': form})

@require_POST
def api_fetch(request):
    """
    Validates the user url input, extracts metadata,
    and schedules a background download task.
    """
    logger.info("Request received: Fetch endpoint called.")
    
    # Run cleanup of files older than 30 minutes
    try:
        cleanup_old_files()
    except Exception as e:
        logger.error(f"Error occurred during automatic file cleanup: {e}")

    # Bind form data
    form = InstagramURLForm(request.POST)
    if not form.is_valid():
        error_msg = form.errors.get('url', ['Invalid input URL.'])[0]
        logger.warning(f"Request failed URL validation: {error_msg}")
        return JsonResponse({'status': 'error', 'message': error_msg}, status=400)

    url = form.cleaned_data['url']

    # Synchronously extract metadata
    try:
        metadata = extract_metadata(url)
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Error during metadata extraction: {error_msg}")
        return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
    except Exception as e:
        logger.error(f"Unexpected metadata extraction exception: {e}")
        return JsonResponse({'status': 'error', 'message': "An unexpected system error occurred. Please try again."}, status=500)

    # Queue download task
    task_id = uuid.uuid4().hex
    logger.info(f"Download started: Queueing task {task_id} in background thread pool.")
    try:
        download_media(url, task_id)
    except Exception as e:
        logger.error(f"Failed to queue background download for task {task_id}: {e}")
        return JsonResponse({'status': 'error', 'message': "Failed to queue media download task."}, status=500)

    return JsonResponse({
        'status': 'success',
        'task_id': task_id,
        'metadata': metadata
    })

@require_GET
def api_status(request, task_id):
    """
    Allows the client to poll the status of a scheduled download task.
    Returns status ('processing', 'completed', 'failed') along with files or error messages.
    """
    task = DOWNLOAD_TASKS.get(task_id)
    if not task:
        logger.warning(f"Status request failed: Task {task_id} not found in cache.")
        return JsonResponse({'status': 'error', 'message': 'Task ID not found.'}, status=404)

    return JsonResponse({
        'status': task['status'],
        'files': task['files'],
        'zip_file': task.get('zip_file'),
        'error': task['error']
    })
