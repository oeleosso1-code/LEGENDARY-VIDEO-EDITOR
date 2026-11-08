import pytest
from app import job_registry,config

def test_lifecycle_and_latest(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    uid=1002
    first=job_registry.create(uid)
    assert job_registry.read(uid,first['id'])['state']=='queued'
    assert job_registry.latest(uid)['id']==first['id']
    job_registry.update(uid,first['id'],state='running',phase='rendering')
    job_registry.update(uid,first['id'],state='completed',phase='finished')
    assert job_registry.read(uid,first['id'])['phase']=='finished'
    with pytest.raises(ValueError):job_registry.update(uid,first['id'],state='running')

def test_user_isolation_and_bad_ids(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    r=job_registry.create(23)
    with pytest.raises(FileNotFoundError):job_registry.read(24,r['id'])
    with pytest.raises(ValueError):job_registry.read(23,'../secrets')
    with pytest.raises(ValueError):job_registry.update(23,r['id'],state='nonsense')

def test_restart_marks_only_incomplete(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    a=job_registry.create(8)
    b=job_registry.create(8)
    job_registry.update(8,a['id'],state='running')
    job_registry.update(8,b['id'],state='running')
    job_registry.update(8,b['id'],state='completed')
    assert job_registry.mark_interrupted(8)==1
    assert job_registry.mark_interrupted(8)==0
    assert job_registry.read(8,a['id'])['state']=='interrupted'
    assert job_registry.read(8,b['id'])['state']=='completed'

def test_no_secrets_in_status(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'OUTPUT_DIR',tmp_path)
    r=job_registry.create(4,preview=True)
    assert set(r)=={'id','state','preview','created_at','updated_at','phase','error'}
    assert r['preview'] is True
