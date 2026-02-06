"""
Tests for Cron Scheduling
"""
import pytest
from pathlib import Path
from datetime import datetime
import json
import asyncio


class TestCronStore:
    """Test cron job persistence."""
    
    def test_cron_job_creation(self, tmp_path):
        """Test creating a cron job."""
        from backend.core.cron_store import CronStore, CronJob
        
        store = CronStore(str(tmp_path / "cron" / "jobs.json"))
        
        job = CronJob(
            id="test-job-1",
            expression="@hourly",
            task="Test task"
        )
        
        store.add_job(job)
        
        # Verify job was added
        loaded_job = store.get_job("test-job-1")
        assert loaded_job is not None
        assert loaded_job.id == "test-job-1"
        assert loaded_job.expression == "@hourly"
        assert loaded_job.task == "Test task"
        assert loaded_job.enabled is True
    
    def test_cron_store_save_load(self, tmp_path):
        """Test saving and loading cron jobs."""
        from backend.core.cron_store import CronStore, CronJob
        
        store_path = str(tmp_path / "cron" / "jobs.json")
        store = CronStore(store_path)
        
        # Add jobs
        store.add_job(CronJob(id="job-1", expression="@daily", task="Daily task"))
        store.add_job(CronJob(id="job-2", expression="@hourly", task="Hourly task"))
        
        # Verify file exists
        assert Path(store_path).exists()
        
        # Create new store instance and load
        store2 = CronStore(store_path)
        jobs = store2.list_jobs()
        
        assert len(jobs) == 2
        job_ids = {j.id for j in jobs}
        assert "job-1" in job_ids
        assert "job-2" in job_ids
    
    def test_cron_job_remove(self, tmp_path):
        """Test removing a cron job."""
        from backend.core.cron_store import CronStore, CronJob
        
        store = CronStore(str(tmp_path / "cron" / "jobs.json"))
        
        store.add_job(CronJob(id="to-remove", expression="@daily", task="Task"))
        assert store.get_job("to-remove") is not None
        
        removed = store.remove_job("to-remove")
        assert removed is True
        assert store.get_job("to-remove") is None
    
    def test_cron_job_update(self, tmp_path):
        """Test updating a cron job."""
        from backend.core.cron_store import CronStore, CronJob
        
        store = CronStore(str(tmp_path / "cron" / "jobs.json"))
        
        job = CronJob(id="update-me", expression="@hourly", task="Original task")
        store.add_job(job)
        
        # Update job
        job.task = "Updated task"
        job.enabled = False
        store.update_job(job)
        
        # Verify update
        loaded = store.get_job("update-me")
        assert loaded.task == "Updated task"
        assert loaded.enabled is False


class TestCronExpression:
    """Test cron expression parsing."""
    
    def test_simple_intervals(self):
        """Test simple interval expressions."""
        from backend.core.cron import validate_cron_expression, calculate_next_run
        
        # Simple intervals should be valid
        assert validate_cron_expression("@hourly") is True
        assert validate_cron_expression("@daily") is True
        assert validate_cron_expression("@weekly") is True
        assert validate_cron_expression("@every 5m") is True
        assert validate_cron_expression("@every 1h") is True
    
    def test_calculate_next_run(self):
        """Test next run calculation."""
        from backend.core.cron import calculate_next_run
        
        now = datetime.now().timestamp()
        
        # @hourly should be ~1 hour from now
        hourly = calculate_next_run("@hourly")
        assert hourly is not None
        assert hourly >= now
        assert hourly <= now + 3700  # Within ~1 hour
        
        # @every 5m should be ~5 minutes from now
        every_5m = calculate_next_run("@every 5m")
        assert every_5m is not None
        assert every_5m >= now
        assert every_5m <= now + 400  # Within ~5 minutes


class TestCronScheduler:
    """Test cron scheduler."""
    
    def test_scheduler_add_job(self, tmp_path):
        """Test adding jobs to scheduler."""
        from backend.core.cron import CronScheduler
        from backend.core.cron_store import CronStore
        
        store = CronStore(str(tmp_path / "cron" / "jobs.json"))
        scheduler = CronScheduler(store=store)
        
        job = scheduler.add_job("@hourly", "Test task")
        
        assert job is not None
        assert job.expression == "@hourly"
        assert job.task == "Test task"
        assert job.next_run is not None
    
    def test_scheduler_enable_disable(self, tmp_path):
        """Test enabling and disabling jobs."""
        from backend.core.cron import CronScheduler
        from backend.core.cron_store import CronStore
        
        store = CronStore(str(tmp_path / "cron" / "jobs.json"))
        scheduler = CronScheduler(store=store)
        
        job = scheduler.add_job("@daily", "Daily task")
        assert scheduler.get_job(job.id).enabled is True
        
        # Disable
        scheduler.disable_job(job.id)
        assert scheduler.get_job(job.id).enabled is False
        
        # Enable
        scheduler.enable_job(job.id)
        assert scheduler.get_job(job.id).enabled is True
    
    def test_scheduler_list_jobs(self, tmp_path):
        """Test listing jobs."""
        from backend.core.cron import CronScheduler
        from backend.core.cron_store import CronStore
        
        store = CronStore(str(tmp_path / "cron" / "jobs.json"))
        scheduler = CronScheduler(store=store)
        
        scheduler.add_job("@hourly", "Task 1")
        scheduler.add_job("@daily", "Task 2")
        scheduler.add_job("@weekly", "Task 3")
        
        jobs = scheduler.list_jobs()
        assert len(jobs) == 3
