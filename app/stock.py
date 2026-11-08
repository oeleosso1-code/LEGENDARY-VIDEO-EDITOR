import httpx
from pathlib import Path
from urllib.parse import urlsplit
from .config import PEXELS_KEY, MAX_SOURCE_BYTES

API = 'https://api.pexels.com/v1/videos/search'

async def find_footage(query: str, vertical: bool, limit: int) -> list[dict]:
    if not PEXELS_KEY:
        raise RuntimeError('PEXELS_API_KEY غير موجود في ملف .env')
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        res = await client.get(API, params={'query': query, 'per_page': min(limit * 2, 40), 'orientation': 'portrait' if vertical else 'landscape'}, headers={'Authorization': PEXELS_KEY})
        res.raise_for_status()
        matches = []
        for video in res.json().get('videos', []):
            files = [f for f in video.get('video_files', []) if f.get('file_type') == 'video/mp4' and f.get('link') and (f.get('width') or 0) >= 640]
            files.sort(key=lambda f: abs((f.get('width') or 1280) - (720 if vertical else 1280)))
            if files:
                matches.append({'url': files[0]['link'], 'creator': video.get('user', {}).get('name','Pexels'), 'page': video.get('url', '')})
            if len(matches) >= limit:
                break
        return matches

async def download_footage(item: dict, dest: Path) -> None:
    url = item['url']
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not (parsed.hostname == 'pexels.com' or (parsed.hostname or '').endswith('.pexels.com')):
        raise ValueError('تم رفض رابط المصدر غير الموثوق.')
    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15), follow_redirects=False) as client:
        async with client.stream('GET', url) as response:
            response.raise_for_status()
            if int(response.headers.get('content-length', '0')) > MAX_SOURCE_BYTES:
                raise RuntimeError('ملف المصدر كبير جداً')
            size = 0
            with dest.open('wb') as fh:
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_SOURCE_BYTES:
                        raise RuntimeError('تم تجاوز الحد الأقصى لتنزيل المصدر')
                    fh.write(chunk)
