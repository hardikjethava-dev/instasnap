from django import forms
import urllib.parse
import re

class InstagramURLForm(forms.Form):
    url = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Paste Instagram link here...',
            'class': 'form-control',
            'id': 'instagram-url-input',
            'autocomplete': 'off'
        })
    )

    def clean_url(self) -> str:
        url = self.cleaned_data.get('url', '').strip()
        if not url:
            raise forms.ValidationError("URL is required.")

        try:
            parsed = urllib.parse.urlparse(url)
            # Standardize scheme if missing
            if not parsed.scheme:
                if not url.startswith('http://') and not url.startswith('https://'):
                    url = 'https://' + url
                    parsed = urllib.parse.urlparse(url)

            if parsed.scheme not in ['http', 'https']:
                raise forms.ValidationError("Invalid URL scheme. Only HTTP and HTTPS are allowed.")

            # Host validation
            host = parsed.netloc.lower()
            if host not in ['instagram.com', 'www.instagram.com']:
                raise forms.ValidationError("Security Error: Only instagram.com or www.instagram.com is allowed.")

            # Path validation
            path = parsed.path
            # Remove double slashes
            path = re.sub(r'/+', '/', path)

            if not (path.startswith('/reel/') or path.startswith('/p/') or path.startswith('/tv/')):
                raise forms.ValidationError("Only Instagram Reels, Photos/Posts, and TV URLs are supported.")

            # Path traversal detection in path
            if '..' in path or '\\' in path:
                raise forms.ValidationError("Invalid characters in URL path.")

        except forms.ValidationError as e:
            raise e
        except Exception as e:
            raise forms.ValidationError(f"Failed to parse URL: {e}")

        return url
