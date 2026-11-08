"""Telegram production controller for real user footage, uploaded music and Pexels stock."""
import asyncio
import json
import copy
import math
import logging
import shutil
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from . import config,store
from .director import plan_queries
from .stock import find_footage, download_footage
from .editor_pro import render_pro, probe
from .visual import inspect_clip
from .integrations import clean_silence, transcribe_srt, IntegrationUnavailable
from .shotlist import parse_shotlist, trim_shotlist
from .auto_timeline import plan_uploaded_sources, write_edit_plan
from .music_director import analyze_music
from .reference_style import inspect_reference
from .vision_director import scan_clips, file_digest

LOG=logging.getLogger(__name__)
RUNNING: dict[int,asyncio.Task]={}
QUEUE=asyncio.Semaphore(1)

HELP=('🎬 LEGENDARY VIDEO EDITOR X33\n'
      '/new وصف الفيديو | المدة بالثواني | vertical أو horizontal | cinematic أو fast أو smooth أو documentary\n'
      'بعد /new أرسل مقاطع الفيديو أو أغنية كملف صوتي (MP3/M4A/WAV).\n'
      '/grade natural|cinematic|vivid|noir|warm|cool لاختيار الألوان. أرسل ملف SRT لإظهار الترجمة على الفيديو.\n'
      '/quality preview|hd|fullhd لتحديد دقة التصدير الطويل ذي جدول لقطات.\n'
      '/volume 0.85 لضبط صوت الأغنية (0 إلى 1.5). /musicstart 10 لبدء الأغنية من الثانية العاشرة. /preview لمعاينة 12 ثانية قبل التصيير النهائي.\n'
      '/shotadd رقم_المقطع البداية المدة السرعة لإضافة لقطة (ترقيم يبدأ من 1). /shots لعرض جدول اللقطات و/shotclear لمسحه. أو ارفع ملف shotlist.json.\n'
      'للعناوين العربية ارفع ملف titles.json مع جدول shotlist.json، ثم /longmake.\n'
      '/referencelast لتعيين آخر فيديو مرجعاً للأسلوب فقط؛ /refinspect لتحليله؛ /usegrade لاعتماد التلوين المقترح.\n'
      '/musicmap لتحليل إيقاع الأغنية المحلية؛ /autoplan لتوليد جدول لقطات من فيديوهاتك وإيقاع الأغنية.\n'
      '/aiscan openai أو /aiscan gemini: تحليل صور مصغرة عبر الخدمة الخارجية بعد تفعيل CLOUD_VISION_ENABLED=1. قد يترتب استهلاك مدفوع.\n'
      '/make للبدء، /inspect لفحص جودة المقاطع، /status للحالة، /cancel لإلغاء المعالجة، /clear لإزالة مواد الجلسة.\n'
      'المقاطع التي ترسلها تستخدم مباشرة؛ وإن لم ترسل مقاطع، يبحث عن لقطات Pexels عند إضافة مفتاحه.\n'
      'استعمل ملفات موسيقى تملك حقوق استخدامها.\n'
      'تليگرام العادي يقيّد تنزيل ملفات المستخدم إلى 20 MB وإرسال الناتج إلى 50 MB تقريباً.')

def authorized(update):
    return bool(update.effective_user) and (not config.ALLOWED_USER_IDS or update.effective_user.id in config.ALLOWED_USER_IDS)

async def guard(update):
    if not authorized(update):
        await update.effective_message.reply_text('غير مصرح لك باستخدام هذا البوت.');return False
    return True

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if await guard(update):await update.message.reply_text(HELP)

async def new(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    body=update.message.text.partition(' ')[2]
    parts=[p.strip() for p in body.split('|')]
    if not parts or not parts[0]:
        await update.message.reply_text('مثال: /new Iraqi nature | 45 | vertical | cinematic');return
    try: seconds=int(parts[1]) if len(parts)>1 and parts[1] else 30
    except ValueError:
        await update.message.reply_text('المدة رقم بالثواني.');return
    if not 5<=seconds<=config.MAX_DURATION:
        await update.message.reply_text(f'المدة المسموحة 5 إلى {config.MAX_DURATION} ثانية.');return
    orientation=parts[2].lower() if len(parts)>2 else 'vertical'
    style=parts[3].lower() if len(parts)>3 else 'cinematic'
    if orientation not in ('vertical','horizontal') or style not in store.ALLOWED_STYLES:
        await update.message.reply_text('الاتجاه vertical/horizontal؛ النمط cinematic/fast/smooth/documentary');return
    d=store.load(update.effective_user.id)
    d.update({'prompt':parts[0][:800],'seconds':seconds,'orientation':orientation,'style':style})
    store.save(update.effective_user.id,d)
    await update.message.reply_text(f'تم ضبط المشروع: {seconds} ثانية، {orientation}، {style}. أرسل الفيديوهات أو الموسيقى، ثم /make.')

async def receive_media(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    msg=update.message
    document=msg.document
    if msg.video:
        file=msg.video; kind='clip'; ext='.mp4'
    elif msg.audio:
        file=msg.audio;kind='music';ext=Path(msg.audio.file_name or 'song.mp3').suffix.lower()
    elif document:
        name=(document.file_name or '').lower()
        ext=Path(name).suffix.lower()
        if ext in ('.mp4','.mov','.mkv','.webm'): kind='clip'
        elif ext in ('.mp3','.wav','.m4a','.aac','.ogg','.flac'):kind='music'
        elif ext=='.srt':kind='subtitles'
        elif ext=='.json' and Path(name).name == 'shotlist.json':kind='shotlist'
        elif ext=='.json' and Path(name).name == 'titles.json':kind='titles'
        else:
            await msg.reply_text('نوع الملف غير مدعوم.');return
        file=document
    else:return
    if kind=='titles' and file.file_size and file.file_size > 64*1024:
        await msg.reply_text('ملف العناوين كبير جداً (الحد 64 KB).');return
    if kind=='shotlist' and file.file_size and file.file_size > 256*1024:
        await msg.reply_text('ملف جدول اللقطات كبير جداً (الحد 256 KB).');return
    if file.file_size and file.file_size > min(config.MAX_UPLOAD_MB,20)*1024*1024:
        await msg.reply_text('حجم الملف يتجاوز حد تنزيل البوت الرسمي. ارفع مقطعاً أصغر أو استخدم خادم Bot API محلياً.');return
    uid=update.effective_user.id; d=store.load(uid)
    if kind=='clip' and len(d['clips'])>=config.MAX_USER_CLIPS:
        await msg.reply_text('وصلت إلى الحد الأقصى لمقاطع هذا المشروع.');return
    path=store.unique_file(uid,ext)
    try:
        tfile=await file.get_file()
        await tfile.download_to_drive(custom_path=str(path),read_timeout=90,write_timeout=90)
        if not path.is_file() or path.stat().st_size==0:raise ValueError('ملف فارغ')
        if kind=='clip':d['clips'].append(str(path));d['ai_analysis']=None
        elif kind=='music':d['music']=str(path)
        elif kind=='subtitles':d['subtitles']=str(path)
        elif kind=='titles':
            from .titles import load_titles
            load_titles(path,d['seconds'])
            d['titles']=str(path)
        else:
            if not d['clips']:
                raise ValueError('أرسل مقاطع الفيديو قبل جدول اللقطات')
            durations=[]
            for source in d['clips']:
                dur,has_video=await probe(Path(source))
                if not has_video: raise ValueError('مقطع غير صالح')
                durations.append(dur)
            parse_shotlist(path,durations,d['seconds'])
            old=d.get('shotlist')
            d['shotlist']=str(path)
            if old and Path(old).parent==store.root(uid) and Path(old)!=path: Path(old).unlink(missing_ok=True)
        store.save(uid,d)
        await msg.reply_text('✅ تمت إضافة '+('مقطع الفيديو' if kind=='clip' else 'الأغنية' if kind=='music' else 'الترجمة' if kind=='subtitles' else 'العناوين' if kind=='titles' else 'جدول اللقطات')+f'. عدد الفيديوهات: {len(d["clips"])}. اكتب /make عند الاستعداد.')
    except Exception as e:
        path.unlink(missing_ok=True)
        LOG.exception('File download failed')
        await msg.reply_text('تعذر استلام الملف: '+str(e)[:180])

async def referencelast(update:Update,context:ContextTypes.DEFAULT_TYPE):
    """Reference clip is explicitly excluded from video source clips."""
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('انتظر انتهاء مهمة التصدير أولاً.');return
    d=store.load(uid)
    if not d.get('clips'):
        await update.message.reply_text('أرسل الفيديو المرجعي أولاً كآخر مقطع، ثم أرسل /referencelast.');return
    path=Path(d['clips'][-1])
    if path.parent!=store.root(uid) or not path.is_file():
        await update.message.reply_text('ملف المرجع غير موجود في مجلد المستخدم.');return
    if d.get('shotlist'):
        await update.message.reply_text('امسح جدول اللقطات قبل تغيير عدد المصادر باستخدام /shotclear.');return
    d['clips'].pop()
    d['reference']=str(path)
    d['reference_profile']=None
    d['ai_analysis']=None
    store.save(uid,d)
    await update.message.reply_text('تم تعيين الفيديو الأخير مرجعاً للأسلوب فقط؛ لن يدخل في لقطات المونتاج.')

async def refinspect(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id
    d=store.load(uid)
    path=Path(d.get('reference') or '')
    if not path.is_file() or path.parent!=store.root(uid):
        await update.message.reply_text('حدد الفيديو المرجعي أولاً بأمر /referencelast.');return
    try:
        profile=await inspect_reference(path)
        d['reference_profile']=profile
        store.save(uid,d)
        await update.message.reply_text(
            f'تحليل بصري مبدئي: متوسط الإضاءة {profile["brightness"]}, '
            f'تغيّرات مشهد كبيرة {len(profile["coarse_cut_times"])}, '
            f'التلوين المقترح: {profile["suggested_grade"]}. '
            'هذا لا ينسخ المؤثرات أو النصوص تلقائياً.')
    except (ValueError,RuntimeError,OSError) as exc:
        await update.message.reply_text('تعذر تحليل المرجع: '+str(exc)[:160])

async def usegrade(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id
    d=store.load(uid)
    profile=d.get('reference_profile') or {}
    color=profile.get('suggested_grade')
    from .editor_pro import COLOR_PRESETS
    if color not in COLOR_PRESETS:
        await update.message.reply_text('حلّل المرجع أولاً: /refinspect');return
    d['color']=color
    store.save(uid,d)
    await update.message.reply_text('اعتمدت إعداد التلوين المقترح: '+color)

async def musicmap(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id
    d=store.load(uid)
    song=Path(d.get('music') or '')
    if not song.is_file() or song.parent!=store.root(uid):
        await update.message.reply_text('أرسل ملف أغنية مسموحاً باستخدامها أولاً.');return
    try:
        profile=await analyze_music(song,music_start=float(d.get('music_start',0)),duration=min(d['seconds'],120))
        await update.message.reply_text(
            f'🎵 تم تحليل {profile["duration_analyzed"]:.1f} ثانية. '
            f'سرعة الإيقاع التقريبية: {profile["tempo_estimate_bpm"] or "غير مؤكدة"} BPM، '
            f'نقاط صوت قوية: {len(profile["onsets"])}. '
            'التحليل تقريبي ولا يحدد كلمات الأغنية أو تصاعدها الفني بصورة مؤكدة.')
    except (ValueError,RuntimeError,OSError) as exc:
        await update.message.reply_text('فشل تحليل الموسيقى: '+str(exc)[:180])

async def aiscan(update:Update,context:ContextTypes.DEFAULT_TYPE):
    """Explicit user command is necessary before any remote image request."""
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('أوقف المهمة الحالية قبل التحليل.');return
    import os
    if os.getenv('CLOUD_VISION_ENABLED','0') != '1':
        await update.message.reply_text('التحليل السحابي معطل على الخادم. يتطلب تفعيله موافقة المشغل في .env.');return
    provider=' '.join(context.args).lower().strip()
    if provider not in ('openai','gemini'):
        await update.message.reply_text('الاستخدام: /aiscan openai أو /aiscan gemini؛ يتم إرسال صور مصغرة للخدمة وقد تُحتسب رسوم.');return
    d=store.load(uid)
    paths=[Path(p) for p in d.get('clips',[])]
    if not paths or any(not p.is_file() or p.parent!=store.root(uid) for p in paths):
        await update.message.reply_text('ارفع المقاطع التي تملك حق استخدامها أولاً.');return
    try:
        results=await scan_clips(paths,prompt=d.get('prompt',''),provider=provider,
                                 consent=True,max_images=min(6,len(paths)))
        d['ai_analysis']=results
        store.save(uid,d)
        categories=', '.join(r['category'] for r in results)
        await update.message.reply_text('تم تحليل '+str(len(results))+' صور مصغرة عبر '+provider+
          '. التصنيفات: '+categories+'. استخدم /autoplan؛ النتائج تقريبية وليست كشف أحداث مؤكد.')
    except Exception as exc:
        LOG.warning('Cloud vision not available: %s',type(exc).__name__)
        await update.message.reply_text('تعذر التحليل السحابي. تحقق من المفتاح والصلاحيات والرصيد ونوع النموذج.')

async def autoplan(update:Update,context:ContextTypes.DEFAULT_TYPE):
    """Propose user-editable cuts; never overwrite sources, reference or current edit."""
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('توجد مهمة تصدير نشطة.');return
    d=store.load(uid)
    sources=[Path(x) for x in d.get('clips',[])]
    if not sources or any(not p.is_file() or p.parent!=store.root(uid) for p in sources):
        await update.message.reply_text('ارفع ملفات الفيديو الأصلية أولاً.');return
    song=Path(d['music']) if d.get('music') else None
    if song and (not song.is_file() or song.parent!=store.root(uid)):
        await update.message.reply_text('ملف الموسيقى غير موجود.');return
    try:
        profile=d.get('reference_profile')
        ranked=d.get('ai_analysis') or []
        priority=None
        if ranked and all(i < len(sources) and ranked[i].get('source_hash')==file_digest(sources[i])
                          for i in range(len(ranked))):
            priority=sorted(range(len(sources)),key=lambda i:-(ranked[i]['relevance']
                         if i<len(ranked) else 0.5))
        plan=await plan_uploaded_sources(sources,d['seconds'],style=d['style'],song=song,
                 music_start=float(d.get('music_start',0)),reference_profile=profile,
                 priority=priority)
        lengths=[(await probe(p))[0] for p in sources]
        path=store.unique_file(uid,'.json')
        write_edit_plan(path,plan,lengths,d['seconds'])
        d['shotlist']=str(path)
        store.save(uid,d)
        await update.message.reply_text(
            f'🎞️ أُنشئ جدول جديد يحتوي على {len(plan["shots"])} لقطة من ملفاتك الحقيقية. '
            'استخدم /shots لمراجعته، ثم /preview أو /longmake. '
            'هذا تخطيط قائم على مؤشرات تقنية وإيقاع تقريبي، وليس فهماً كاملاً للأحداث.')
    except (ValueError,RuntimeError,OSError) as exc:
        await update.message.reply_text('فشل تخطيط اللقطات: '+str(exc)[:230])

async def quality(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('لا يمكن تغيير الدقة أثناء التصدير.');return
    choice=' '.join(context.args).strip().lower()
    if choice not in ('preview','hd','fullhd'):
        await update.message.reply_text('الخيارات: /quality preview أو /quality hd أو /quality fullhd');return
    d=store.load(uid)
    d['quality']=choice
    store.save(uid,d)
    await update.message.reply_text('تم ضبط جودة التصدير الطويل: '+choice+'. وضع HD يحتاج موارد خادم أعلى وجدول لقطات.')

async def grade(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    from .editor_pro import COLOR_PRESETS
    name=' '.join(context.args).strip().lower()
    if name not in COLOR_PRESETS:
        await update.message.reply_text('اختر: '+', '.join(COLOR_PRESETS));return
    d=store.load(update.effective_user.id)
    d['color']=name
    store.save(update.effective_user.id,d)
    await update.message.reply_text(f'تم اعتماد تلوين {name} للتصدير القادم.')

async def volume(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    try:
        value=float(' '.join(context.args).strip())
        if not 0 <= value <= 1.5: raise ValueError
    except ValueError:
        await update.message.reply_text('مثال: /volume 0.8 (القيمة بين 0 و1.5)');return
    d=store.load(update.effective_user.id)
    d['music_volume']=value
    store.save(update.effective_user.id,d)
    await update.message.reply_text(f'تم ضبط صوت الموسيقى على {value:.2f}')

async def musicstart(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    try:
        value=float(' '.join(context.args).strip())
        import math
        if not math.isfinite(value) or value < 0 or value > 36000: raise ValueError
    except ValueError:
        await update.message.reply_text('مثال: /musicstart 15 (الثواني، من 0 إلى 36000)');return
    d=store.load(update.effective_user.id)
    d['music_start']=value
    store.save(update.effective_user.id,d)
    await update.message.reply_text(f'سيبدأ تشغيل الملف الموسيقي من الثانية {value:g}.')

async def shots(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    d=store.load(update.effective_user.id)
    path=d.get('shotlist')
    if not path or not Path(path).is_file():
        await update.message.reply_text('لا يوجد جدول لقطات. أضف: /shotadd 1 0 3 1 أو ارفع shotlist.json.');return
    try:
        data=json.loads(Path(path).read_text('utf-8'))['shots']
        lines=[f'🎞️ جدول اللقطات: {len(data)} | الإجمالي {sum(float(x["duration"]) for x in data):.2f} ثانية']
        lines.extend(f'{i}. مقطع {x["clip"]+1} | البداية {x["start"]:g} | المدة {x["duration"]:g} | السرعة {x["speed"]:g}x' for i,x in enumerate(data[:30],1))
        if len(data)>30:lines.append(f'... و{len(data)-30} لقطة إضافية')
        await update.message.reply_text('\n'.join(lines)[:3900])
    except (OSError, ValueError, KeyError, TypeError):
        await update.message.reply_text('ملف اللقطات غير قابل للقراءة.')

async def shotadd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('لا يمكن تغيير الجدول أثناء معالجة الفيديو.');return
    d=store.load(uid)
    try:
        if len(context.args) not in (3,4):raise ValueError
        index=int(context.args[0])-1
        start=float(context.args[1]); duration=float(context.args[2])
        speed=float(context.args[3]) if len(context.args)==4 else 1.0
        if index<0 or index>=len(d['clips']) or not all(math.isfinite(x) for x in (start,duration,speed)):
            raise ValueError
        if start<0 or duration<0.15 or not 0.25<=speed<=4:raise ValueError
    except ValueError:
        await update.message.reply_text('الاستخدام: /shotadd 1 0 3 1.5\nرقم المقطع (يبدأ من 1)، بداية المصدر، مدة الإخراج، السرعة.');return
    previous=d.get('shotlist')
    path=Path(previous) if previous and Path(previous).parent==store.root(uid) else store.root(uid)/'shotlist.json'
    try:
        data=json.loads(path.read_text('utf-8'))['shots'] if path.is_file() else []
        if len(data)>=2400:raise ValueError('الحد الأقصى 2400 لقطة')
        src=Path(d['clips'][index]); srcdur,hasvideo=await probe(src)
        if not hasvideo or start+duration*speed>srcdur+0.05:
            raise ValueError('المقطع أقصر من الوقت المطلوب بعد حساب السرعة')
        data.append({'clip':index,'start':start,'duration':duration,'speed':speed})
        # Partial shotlists may be created incrementally. Validate entire sequence on /make.
        tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'shots':data},ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.replace(path)
        d['shotlist']=str(path);store.save(uid,d)
        total=sum(s['duration'] for s in data)
        await update.message.reply_text(f'أضفت اللقطة {len(data)}. إجمالي الجدول {total:.2f} ثانية؛ مدة المشروع {d["seconds"]} ثانية. يجب أن تتساوى المدتان قبل /make.')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        await update.message.reply_text('تعذر إضافة اللقطة: '+str(exc)[:180])

async def shotclear(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('أوقف المعالجة أولاً.');return
    d=store.load(uid);path=d.get('shotlist')
    if path and Path(path).parent==store.root(uid):Path(path).unlink(missing_ok=True)
    d['shotlist']=None;store.save(uid,d)
    await update.message.reply_text('تم مسح جدول اللقطات؛ سيعود الاختيار التلقائي.')

async def validate_user_shotlist(uid:int,d:dict):
    shotpath=d.get('shotlist')
    if not shotpath:return None
    path=Path(shotpath)
    if not path.is_file() or path.parent!=store.root(uid):
        raise ValueError('ملف جدول اللقطات مفقود أو غير مصرح')
    durations=[]
    for entry in d['clips']:
        source=Path(entry)
        if source.parent!=store.root(uid) or not source.is_file():raise ValueError('ملف فيديو مفقود')
        dur,hasvideo=await probe(source)
        if not hasvideo:raise ValueError('مصدر فيديو غير صالح')
        durations.append(dur)
    return parse_shotlist(path,durations,d['seconds'])

async def preview(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('هناك مهمة قيد التنفيذ.');return
    d=store.load(uid)
    if not d.get('clips'):
        await update.message.reply_text('للمعاينة أرسل مقطع فيديو واحداً على الأقل أولاً. البحث من الإنترنت متاح مع /make.');return
    try:await validate_user_shotlist(uid,d)
    except (ValueError,OSError) as exc:
        await update.message.reply_text('الجدول غير صالح: '+str(exc));return
    d=copy.deepcopy(d)
    d['original_seconds']=d['seconds']
    d['seconds']=min(12,d['seconds'])
    await update.message.reply_text('🎬 بدأت معالجة معاينة منخفضة الدقة (حتى 12 ثانية).')
    RUNNING[uid]=asyncio.create_task(process_job(context.bot,update.effective_chat.id,uid,d,preview_mode=True))

async def status(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id;d=store.load(uid);t=RUNNING.get(uid)
    await update.message.reply_text(f'الوصف: {d["prompt"] or "لم يحدد"}\nالمدة: {d["seconds"]} ثانية\nاللقطات: {len(d["clips"])}\nموسيقى: {"نعم" if d["music"] else "لا"}\nالألوان: {d.get("color","natural")}\nترجمة: {"نعم" if d.get("subtitles") else "لا"}\nالمعالجة: {"نشطة" if t and not t.done() else "متوقفة"}')

async def inspect(update:Update,context:ContextTypes.DEFAULT_TYPE):
    """Report objective sampled visual metrics; not a human quality judgement."""
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('الفحص غير متاح أثناء تصيير فيديو في الجلسة نفسها.');return
    data=store.load(uid)
    clips=[Path(p) for p in data.get('clips',[]) if Path(p).is_file() and Path(p).parent==store.root(uid)]
    if not clips:
        await update.message.reply_text('ارسل فيديو أولاً، ثم استخدم /inspect.');return
    results=[]
    for p in clips[:min(10,config.MAX_USER_CLIPS)]:
        try:
            dur,has_video=await probe(p)
            if not has_video:continue
            metrics=await inspect_clip(p,dur,data.get('style','cinematic'))
            results.append((p.name[:12],metrics))
        except Exception as exc:
            LOG.warning('Inspect failed for %s: %s',p,exc)
    if not results:
        await update.message.reply_text('تعذر تحليل الملفات. تحقق من سلامة الفيديوهات.');return
    lines=['🔎 فحص آلي أولي (مؤشرات تقنية لا تساوي جودة المونتاج):']
    for name,m in sorted(results,key=lambda r:r[1]['score'],reverse=True):
        lines.append(f'{name}: {m["score"]:.2f}/1 | إضاءة {m.get("brightness",0):.0f} | حركة {m.get("motion",0):.0f}')
    await update.message.reply_text('\n'.join(lines)[:3900])

async def clear(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('ألغِ المشروع الجاري باستخدام /cancel أولاً.');return
    old=store.load(uid)
    for s in old.get('clips',[])+([old['music']] if old.get('music') else [])+([old['subtitles']] if old.get('subtitles') else [])+([old['shotlist']] if old.get('shotlist') else [])+([old['titles']] if old.get('titles') else [])+([old['reference']] if old.get('reference') else []):
        p=Path(s)
        if p.parent==store.root(uid):p.unlink(missing_ok=True)
    store.save(uid,store.blank())
    await update.message.reply_text('حُذفت ملفات الإدخال الخاصة بالجلسة الحالية وأعيد ضبط الإعدادات. ملفات التصيير السابقة محفوظة على الخادم.')

async def make(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    uid=update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('هناك مشروع قيد التنفيذ. استخدم /status أو /cancel.');return
    d=store.load(uid)
    if not d['prompt'] and not d['clips']:
        await update.message.reply_text('ابدأ بـ /new أو أرسل مقطع فيديو.');return
    try:await validate_user_shotlist(uid,d)
    except (ValueError,OSError) as exc:
        await update.message.reply_text('جدول اللقطات غير صالح: '+str(exc));return
    await update.message.reply_text('🎬 تم استقبال المهمة. سيُرسل إشعار عند اكتمال التصدير.')
    RUNNING[uid]=asyncio.create_task(process_job(context.bot,update.effective_chat.id,uid,copy.deepcopy(d)))

async def cancel(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if not await guard(update):return
    t=RUNNING.get(update.effective_user.id)
    if not t or t.done():await update.message.reply_text('لا توجد مهمة نشطة.');return
    t.cancel()
    await update.message.reply_text('طلب إلغاء المهمة. قد تستمر عملية FFmpeg الحالية حتى تنتهي إذا كانت قيد التنفيذ.')

async def process_job(bot, chat_id:int,uid:int,d:dict,preview_mode:bool=False):
    async with QUEUE:
        job=store.job_dir(uid)
        credits=[]
        try:
            if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
                raise RuntimeError('FFmpeg وFFprobe غير مثبتين على الخادم')
            sources=[Path(s) for s in d['clips'] if Path(s).is_file() and Path(s).parent==store.root(uid)]
            if not sources:
                if not config.PEXELS_KEY:raise RuntimeError('أرسل فيديوهات أو ضع PEXELS_API_KEY في ملف .env')
                terms=await plan_queries(d['prompt'],5)
                await bot.send_message(chat_id,'🔎 البحث عن لقطات حقيقية مناسبة...')
                count=min(config.MAX_CLIPS,max(2,min(12,(d['seconds']+8)//9)))
                for term in terms[:3]:
                    items=await find_footage(term,d['orientation']=='vertical',count)
                    for item in items:
                        if len(sources)>=count:break
                        p=job/f'asset_{len(sources):03}.mp4'
                        try:
                            await download_footage(item,p)
                            sources.append(p)
                            credits.append({'creator':item.get('creator','Pexels'),'page':item.get('page','')})
                        except Exception as e:LOG.warning('Asset failed %s',e)
                    if len(sources)>=count:break
            if not sources:raise RuntimeError('لا توجد لقطات قابلة للاستخدام')
            song=Path(d['music']) if d.get('music') else None
            if song and (not song.is_file() or song.parent!=store.root(uid)):song=None
            await bot.send_message(chat_id,f'🎞️ بدأت معالجة {len(sources)} لقطة، والموسيقى: {"مضافة" if song else "غير مضافة"}.')
            if config.SILENCE_CLEANUP and d['style']=='documentary':
                cleaned=[]
                for index, src in enumerate(sources):
                    dest_clean=job/f'cleaned_{index:03d}.mp4'
                    try: cleaned.append(await clean_silence(src,dest_clean))
                    except (IntegrationUnavailable,RuntimeError) as exc:
                        LOG.warning('Silence cleanup skipped: %s',exc)
                        cleaned.append(src)
                sources=cleaned
            manual_path=None
            if d.get('shotlist'):
                shots=await validate_user_shotlist(uid,{**d,'seconds':d.get('original_seconds',d['seconds'])})
                if preview_mode:shots=trim_shotlist(shots,d['seconds'])
                manual_path=job/'shotlist.json'
                manual_path.write_text(json.dumps({'shots':shots},ensure_ascii=False,indent=2),encoding='utf-8')
            dest=job/'final.mp4'
            subtitle=Path(d['subtitles']) if d.get('subtitles') else None
            if subtitle and (not subtitle.is_file() or subtitle.parent!=store.root(uid)): subtitle=None
            await render_pro(sources,song,dest,d['seconds'],d['orientation'],d['style'],color=d.get('color','natural'),subtitles=subtitle,music_volume=float(d.get('music_volume',0.85)),preview=preview_mode,music_start=float(d.get('music_start',0.0)),shotlist=manual_path)
            if config.WHISPER_MODEL and not preview_mode:
                try:
                    srt=await transcribe_srt(dest,job/'subtitles',Path(config.WHISPER_MODEL))
                    await bot.send_document(chat_id,document=srt.open('rb'),filename='subtitles.srt',caption='ترجمة نصية تلقائية، راجع دقتها قبل النشر')
                except (IntegrationUnavailable,RuntimeError) as exc:
                    LOG.warning('Subtitles unavailable: %s',exc)
            (job/'sources.json').write_text(json.dumps(credits,ensure_ascii=False,indent=2),encoding='utf-8')
            size=dest.stat().st_size
            if size<=49*1024*1024:
                with dest.open('rb') as stream:
                    await bot.send_video(chat_id,video=stream,caption=('🎬 معاينة منخفضة الدقة؛ استخدم /make للتصدير الكامل.' if preview_mode else '✅ مونتاج مكتمل. المصدر: ملفاتك أو Pexels. راجع الحقوق قبل النشر.'),supports_streaming=True,read_timeout=120,write_timeout=120)
            else:
                await bot.send_message(chat_id,f'✅ تم التصدير ({size/1024/1024:.1f} MB). الحجم أكبر من حد إرسال بوت تليگرام العادي. الملف محفوظ على الخادم باسم {job.name}/final.mp4؛ يلزم إعداد تخزين سحابي لإرساله كرابط.')
            if credits:
                await bot.send_message(chat_id,'مصادر اللقطات: Pexels\n'+'\n'.join(x['page'] for x in credits[:12])[:3200])
        except asyncio.CancelledError:
            await bot.send_message(chat_id,'تم إلغاء المهمة.');raise
        except Exception as e:
            LOG.exception('Job error')
            await bot.send_message(chat_id,'تعذر تنفيذ المهمة: '+str(e)[:300])
        finally:
            if RUNNING.get(uid) is asyncio.current_task():RUNNING.pop(uid,None)


# Persistent long-render command layer. Uses a frozen request snapshot on resume.
from . import long_jobs
from .resume_render import render_resumable
from .timeline_render import render_timeline
import os
import uuid

async def process_long_job(bot, chat_id: int, uid: int, req: dict):
    try:
        async with QUEUE:
            output, work = long_jobs.paths(uid, req)
            output.parent.mkdir(parents=True, exist_ok=True)
            if req.get('shotlist'):
                work.mkdir(parents=True, exist_ok=True)
                state_path = work / 'timeline_status.json'
                def progress(state):
                    temp = work / ('status-' + uuid.uuid4().hex + '.tmp')
                    temp.write_text(json.dumps(state), encoding='utf-8')
                    os.replace(temp, state_path)
                progress({'state':'running','finished':0,'total':0})
                try:
                    await render_timeline([Path(x) for x in req['clips']], Path(req['shotlist']), output,
                        music=Path(req['music']) if req.get('music') else None,
                        music_start=req['music_start'], music_volume=req['music_volume'],
                        orientation=req['orientation'], color=req['color'],
                        subtitles=Path(req['subtitles']) if req.get('subtitles') else None,
                        titles=Path(req['titles']) if req.get('titles') else None,
                        quality=req.get('quality','preview'), progress_callback=progress)
                except BaseException:
                    previous = json.loads(state_path.read_text('utf-8'))
                    progress({**previous, 'state':'interrupted'})
                    raise
            else:
                await render_resumable([Path(x) for x in req['clips']],
                    Path(req['music']) if req.get('music') else None,
                    output, req['seconds'], work,
                    orientation=req['orientation'],style=req['style'],color=req['color'],
                    music_start=req['music_start'],music_volume=req['music_volume'])
            if output.stat().st_size <= 49 * 1024 * 1024:
                with output.open('rb') as f:
                    await bot.send_video(chat_id, video=f, caption='تم التصدير بنجاح')
            else:
                await bot.send_message(chat_id, 'اكتمل التصدير؛ الملف كبير ومحفوظ على الخادم ويحتاج إلى خدمة تسليم آمنة.')
    except asyncio.CancelledError:
        await bot.send_message(chat_id, 'تم إيقاف المهمة؛ الأجزاء المكتملة محفوظة للاستئناف.')
        raise
    except Exception as exc:
        LOG.exception('Long rendering failed')
        await bot.send_message(chat_id, 'تعذّر التصدير: ' + str(exc)[:250])
    finally:
        if RUNNING.get(uid) is asyncio.current_task():
            RUNNING.pop(uid, None)

async def longmake(update, context):
    if not await guard(update): return
    uid = update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('هناك مهمة قيد التنفيذ.'); return
    try:
        req = long_jobs.create(uid, store.load(uid))
    except (ValueError, OSError) as exc:
        await update.message.reply_text('طلب غير صالح: '+str(exc)); return
    await update.message.reply_text('تم حفظ طلب الفيديو الطويل وبدء معالجته وفق جدول اللقطات المعتمد، إن وُجد.')
    RUNNING[uid] = asyncio.create_task(process_long_job(context.bot, update.effective_chat.id, uid, req))

async def longstatus(update, context):
    if not await guard(update): return
    uid = update.effective_user.id
    try:
        value = long_jobs.status(uid)
    except (ValueError, OSError) as exc:
        await update.message.reply_text('لا توجد مهمة محفوظة: '+str(exc)); return
    active = uid in RUNNING and not RUNNING[uid].done()
    state = value['state']
    if state == 'running' and not active: state = 'interrupted'
    await update.message.reply_text(f'حالة المهمة: {state}. أجزاء مكتملة {value["finished"]}/{value["total"]}.')

async def longresume(update, context):
    if not await guard(update): return
    uid = update.effective_user.id
    if uid in RUNNING and not RUNNING[uid].done():
        await update.message.reply_text('هناك مهمة قيد التنفيذ.'); return
    try:
        req = long_jobs.load(uid)
    except (ValueError, OSError) as exc:
        await update.message.reply_text('تعذر الاستئناف: '+str(exc)); return
    await update.message.reply_text('بدأ استئناف المهمة من طلبها المحفوظ.')
    RUNNING[uid] = asyncio.create_task(process_long_job(context.bot, update.effective_chat.id, uid, req))

async def connections(update, context):
    """Show configured providers without displaying token, keys or suffixes."""
    if not await guard(update): return
    from .openai_keys import configured_openai_keys
    keys = configured_openai_keys()
    await update.message.reply_text(
        'حالة الربط (من دون عرض الأسرار):\n'
        f'تليگرام: {"مُعد" if config.TOKEN else "غير مُعد"}\n'
        f'OpenAI الأساسي: {"مُعد" if len(keys)>0 else "غير مُعد"}\n'
        f'OpenAI الاحتياطي: {"مُعد" if len(keys)>1 else "غير مُعد"}\n'
        'هذه حالة الإعداد فقط، وليست اختبار اتصال حي.')

def main():
    logging.basicConfig(level=logging.INFO)
    if not config.TOKEN:raise RuntimeError('أدخل TELEGRAM_BOT_TOKEN داخل .env')
    app=Application.builder().token(config.TOKEN).build()
    for cmd,fn in [('start',start),('help',start),('new',new),('make',make),('preview',preview),('volume',volume),('musicstart',musicstart),('status',status),('grade',grade),('inspect',inspect),('clear',clear),('cancel',cancel),('longmake',longmake),('longstatus',longstatus),('longresume',longresume),('connections',connections),('autoplan',autoplan),('aiscan',aiscan),('quality',quality),('musicmap',musicmap),('referencelast',referencelast),('refinspect',refinspect),('usegrade',usegrade),('shots',shots),('shotadd',shotadd),('shotclear',shotclear)]:app.add_handler(CommandHandler(cmd,fn))
    app.add_handler(MessageHandler(filters.VIDEO | filters.AUDIO | filters.Document.ALL,receive_media))
    app.run_polling(drop_pending_updates=True)

if __name__=='__main__':main()
