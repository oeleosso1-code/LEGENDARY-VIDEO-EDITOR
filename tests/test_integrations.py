import asyncio
from pathlib import Path
import pytest
from app import integrations


def test_scene_integration_missing_dependency(monkeypatch, tmp_path):
    # Integration has an explicit installation diagnostic instead of silently claiming success.
    import builtins
    real_import = builtins.__import__
    def fake_import(name, *args, **kwargs):
        if name == 'scenedetect':
            raise ImportError('not installed')
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins,'__import__',fake_import)
    with pytest.raises(integrations.IntegrationUnavailable):
        integrations.scene_boundaries(tmp_path / 'video.mp4')


def test_auto_editor_missing(monkeypatch,tmp_path):
    monkeypatch.setattr(integrations.shutil, 'which', lambda name: None)
    with pytest.raises(integrations.IntegrationUnavailable):
        asyncio.run(integrations.clean_silence(tmp_path/'clip.mp4',tmp_path/'out.mp4'))


def test_whisper_missing(monkeypatch,tmp_path):
    monkeypatch.setattr(integrations.shutil, 'which', lambda name: None)
    with pytest.raises(integrations.IntegrationUnavailable):
        asyncio.run(integrations.transcribe_srt(tmp_path/'clip.mp4',tmp_path/'subs',tmp_path/'model.bin'))
