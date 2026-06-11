from django.test import TestCase, Client
from django.urls import reverse
from downloader.forms import InstagramURLForm
from downloader.services import validate_instagram_url

class InstagramDownloaderTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_validate_instagram_url_success(self):
        """Verify that valid Instagram URLs return True."""
        valid_urls = [
            "https://www.instagram.com/reel/C8xYzZuy7rS/",
            "https://instagram.com/p/CGy47x9H0F_/",
            "https://www.instagram.com/tv/CXe4s5jF_1_/",
            "http://www.instagram.com/p/B-1k8rXHp4f",
        ]
        for url in valid_urls:
            self.assertTrue(validate_instagram_url(url), f"Should be valid: {url}")

    def test_validate_instagram_url_failures(self):
        """Verify that invalid hosts or invalid paths return False."""
        invalid_urls = [
            "https://www.facebook.com/reel/123",
            "https://instagram.com/stories/username/",
            "https://www.instagram.com/direct/inbox/",
            "https://www.instagram.com/p/../admin/",
            "https://www.instagram.com/reel/..\\Traversal",
            "http://evil-instagram.com/p/CGy47x9H0F_/",
            "",
            None,
        ]
        for url in invalid_urls:
            self.assertFalse(validate_instagram_url(url), f"Should be invalid: {url}")

    def test_url_form_validation(self):
        """Test form cleaning and validation constraints."""
        # Test valid input
        form = InstagramURLForm(data={'url': 'instagram.com/reel/C8xYzZuy7rS/'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['url'], 'https://instagram.com/reel/C8xYzZuy7rS/')

        # Test invalid host
        form = InstagramURLForm(data={'url': 'https://evil.com/p/123'})
        self.assertFalse(form.is_valid())
        self.assertIn('url', form.errors)

        # Test path traversal block
        form = InstagramURLForm(data={'url': 'https://instagram.com/p/../etc/passwd'})
        self.assertFalse(form.is_valid())

    def test_views_status_codes(self):
        """Test that application views return correct status codes."""
        # Index view renders
        response = self.client.get(reverse('downloader:index'))
        self.assertEqual(response.status_code, 200)

        # Fetch API rejects GET
        response = self.client.get(reverse('downloader:api_fetch'))
        self.assertEqual(response.status_code, 405)

        # Fetch API rejects empty POST
        response = self.client.post(reverse('downloader:api_fetch'), data={})
        self.assertEqual(response.status_code, 400)

        # Status API returns 404 for unknown task ID
        response = self.client.get(reverse('downloader:api_status', args=['non_existent_id']))
        self.assertEqual(response.status_code, 404)
