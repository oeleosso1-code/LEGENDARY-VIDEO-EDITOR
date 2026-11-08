import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from . import config
from .planner import parse_request
from .stock import find_footage, download_footage
from .editor import render

log = logging.getLogger(__name__)
LOCK = asyncio.Semaphore(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('🎬 LEGENDARY AI VIDEO STUDIO X1\nاكتب مثلاً:\n/make ocean waves | 30 | vertical\nأو:\n/make ancient city | 60 | horizontal\nالنسخة الأولية تجمع لقطات مرخّصة وتدمجها بدون تعليق صوتي. تحتاج إلى تشغيل البرنامج على خادم مثبت عليه FFmpeg.')

async def make(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if config.ALLOWED_USER_IDS and update.effective_user.id not in config.ALLOWED_USER_IDS:
        await update.message.reply_text('هذا البوت مخصص لمستخدمين مصرح لهم.')
        return
    try:
        request = parse_request(update.message.text)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return
    if LOCK.locked():
        await update.message.reply_text('محرك المونتاج مشغول بطلب آخر. حاول لاحقاً.')
        return
    await update.message.reply_text('🔎 أبحث عن لقطات مناسبة وأحضّر المونتاج...')
    async with LOCK:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='studio-', dir=config.OUTPUT_DIR) as tmp:
            folder = Path(tmp)
            try:
                if shutil.which('ffmpeg') is None:
                    raise RuntimeError('FFmpeg غير مثبت على الخادم.')
                items = await find_footage(request.search, request.vertical, min(config.MAX_CLIPS, max(2, (request.duration + 11) // 12)))
                if not items:
                    await update.message.reply_text('لم أجد لقطات مطابقة. جرّب كلمات بحث إنجليزية أقصر.')
                    return
                downloaded = []
                sources = []
                for n, item in enumerate(items):
                    filename = folder / f'source_{n:03}.mp4'
                    try:
                        await download_footage(item, filename)
                        downloaded.append(filename)
                        sources.append({'creator': item['creator'], 'url': item['page']})
                    except Exception as e:
                        log.warning('Skipped source: %s', e)
                if not downloaded:
                    raise RuntimeError('تعذّر تحميل المقاطع المتاحة.')
                output = folder / 'video.mp4'
                await render(downloaded, output, request)
                (folder / 'credits.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding='utf-8')
                caption = '🎬 الفيديو جاهز. مواد الفيديو: Pexels (https://www.pexels.com/)\n' + '\n'.join(f"{s['creator']}: {s['url']}" for s in sources[:3])
                if output.stat().st_size <= 49 * 1024 * 1024:
                    with output.open('rb') as f:
                        await update.message.reply_video(video=f, caption=caption[:1024], supports_streaming=True, read_timeout=120, write_timeout=120)
                else:
                    await update.message.reply_text('الفيديو تجاوز حد الإرسال المباشر لبوت تليگرام (50 MB). يلزم إضافة تخزين خارجي وروابط تحميل لهذه الحالة.')
                await update.message.reply_text('مصادر اللقطات: ' + '\n'.join(s['url'] for s in sources)[:3500])
            except Exception as exc:
                log.exception('Render failed')
                await update.message.reply_text(f'تعذّر تنفيذ المونتاج: {str(exc)[:400]}')

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if not config.TOKEN:
        raise RuntimeError('ضع TELEGRAM_BOT_TOKEN في ملف .env')
    app = Application.builder().token(config.TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('make', make))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
