import re
from dataclasses import dataclass
from .config import MAX_DURATION

@dataclass(frozen=True)
class VideoRequest:
    search: str
    duration: int
    vertical: bool


def parse_request(text: str) -> VideoRequest:
    """/make query | duration seconds | vertical/horizontal; optional natural duration hints."""
    raw = re.sub(r'^/make(?:@\w+)?\s*', '', text.strip(), flags=re.I)
    pieces = [p.strip() for p in raw.split('|')]
    query = pieces[0].strip()
    if not query:
        raise ValueError('اكتب موضوع الفيديو بعد /make، مثل: /make ocean | 30 | vertical')
    seconds = 30
    if len(pieces) > 1 and pieces[1]:
        if not pieces[1].isdigit():
            raise ValueError('المدة يجب أن تكون بالثواني، مثل 30 أو 60.')
        seconds = int(pieces[1])
    else:
        match = re.search(r'(\d{1,4})\s*(?:ثانية|ثواني|seconds|sec)\b', query, re.I)
        if match:
            seconds = int(match.group(1))
    if not 5 <= seconds <= MAX_DURATION:
        raise ValueError(f'مدة النسخة الأولية بين 5 و{MAX_DURATION} ثانية.')
    vertical = any(word in (pieces[2].lower() if len(pieces) > 2 else query.lower()) for word in ('vertical', 'عمودي', 'ريلز', 'shorts', '9:16'))
    return VideoRequest(search=query, duration=seconds, vertical=vertical)
