# backend/scheduler.py
from apscheduler.schedulers.blocking import BlockingScheduler
from birthday_task import run_daily_birthday_task
from datetime import datetime

scheduler = BlockingScheduler()

# Schedule: daily at 7:00 AM
@scheduler.scheduled_job('cron', hour=7, minute=0)
def scheduled_birthday_job():
    print(f"🕖 Scheduled job started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    run_daily_birthday_task()

if __name__ == "__main__":
    print("🚀 Birthday Scheduler is running...")
    scheduler.start()
