"""Offline handler tests can run without Telegram SDK installed.

This is TEST-ONLY: deployment still requires python-telegram-bot from
requirements.txt, and these stubs do not assert live API compatibility.
"""
import importlib.util
import sys
import types
from importlib.machinery import ModuleSpec

if importlib.util.find_spec('telegram') is None and 'telegram' not in sys.modules:
    telegram=types.ModuleType('telegram')
    telegram.__spec__=ModuleSpec('telegram',loader=None)
    telegram.Update=type('Update',(),{})
    ext=types.ModuleType('telegram.ext')
    for name in ('Application','CommandHandler','MessageHandler','ContextTypes'):
        setattr(ext,name,type(name,(),{}))
    ext.ContextTypes.DEFAULT_TYPE=object
    ext.filters=types.SimpleNamespace(VIDEO=0,AUDIO=0,Document=types.SimpleNamespace(ALL=0))
    sys.modules['telegram']=telegram
    sys.modules['telegram.ext']=ext
