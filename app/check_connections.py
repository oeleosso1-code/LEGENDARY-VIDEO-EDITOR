"""Private local environment/connection checker; never prints credentials.

Usage: python -m app.check_connections [--live]
Live mode calls only the provider's authentication endpoints, not billed generation.
"""
import argparse
import asyncio
import httpx
from . import config
from .openai_keys import configured_openai_keys


async def _test_url(client: httpx.AsyncClient, method: str, url: str, headers: dict | None = None) -> str:
    try:
        response = await client.request(method, url, headers=headers)
        if response.status_code == 200:
            return 'الاتصال ناجح'
        return f'فشل التحقق (HTTP {response.status_code})'
    except httpx.HTTPError:
        # Deliberately avoid rendering exception details that may include a bot-token URL.
        return 'تعذّر الاتصال بالشبكة'


async def inspect(*, live: bool = False) -> list[str]:
    keys = configured_openai_keys()
    results = [
        f'تليگرام: {"إعداد موجود" if config.TOKEN else "غير معد"}',
        f'OpenAI الأساسي: {"إعداد موجود" if keys else "غير معد"}',
        f'OpenAI الاحتياطي: {"إعداد موجود" if len(keys) > 1 else "غير معد"}',
    ]
    if not config.ALLOWED_USER_IDS:
        results.append('تنبيه: ALLOWED_USER_IDS فارغ؛ البوت غير مقيد بمستخدم محدد.')
    if not live:
        results.append('هذه مراجعة إعدادات فقط. استخدم --live للتحقق من المصادقة على الجهاز الذي يشغّل المشروع.')
        return results
    async with httpx.AsyncClient(timeout=12) as client:
        if config.TOKEN:
            state = await _test_url(client, 'POST', f'https://api.telegram.org/bot{config.TOKEN}/getMe')
            results.append('فحص تليگرام: ' + state)
        for idx, key in enumerate(keys, 1):
            state = await _test_url(client, 'GET', 'https://api.openai.com/v1/models',
                                    {'Authorization': 'Bearer ' + key})
            results.append(f'فحص OpenAI #{idx}: {state}')
    results.append('فحص المصادقة لا يؤكد صلاحية النموذج المختار أو جودة المونتاج.')
    return results


def main():
    parser = argparse.ArgumentParser(description='Check Telegram and two OpenAI API key connections')
    parser.add_argument('--live', action='store_true', help='Test provider authentication over HTTPS')
    args = parser.parse_args()
    for line in asyncio.run(inspect(live=args.live)):
        print(line)


if __name__ == '__main__':
    main()
