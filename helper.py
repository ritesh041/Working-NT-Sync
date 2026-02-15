import requests
import json
import os
import sys
import subprocess
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Configuration
NOTION_API_TOKEN = os.getenv('NOTION_API_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
TODOIST_API_TOKEN = os.getenv('TODOIST_API_TOKEN')

# Validate tokens on startup
if not NOTION_API_TOKEN or not NOTION_DATABASE_ID or not TODOIST_API_TOKEN:
    logger.error("❌ Missing environment variables. Please check your .env file.")
    logger.error("Required: NOTION_API_TOKEN, NOTION_DATABASE_ID, TODOIST_API_TOKEN")
    sys.exit(1)

notion_headers = {
    'Authorization': f'Bearer {NOTION_API_TOKEN}',
    'Content-Type': 'application/json',
    'Notion-Version': '2022-06-28'
}

todoist_headers = {
    'Authorization': f'Bearer {TODOIST_API_TOKEN}',
    'Content-Type': 'application/json'
}

def cls():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_notion_tasks():
    url = f'https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query'
    try:
        response = requests.post(url, headers=notion_headers, timeout=10)
        
        if response.status_code == 401:
            logger.error("❌ Invalid Notion API token")
            sys.exit(1)
        if response.status_code == 400:
            logger.error("❌ Invalid Notion Database ID")
            sys.exit(2)
        
        response.raise_for_status()
        logger.info(f"✅ Fetched tasks from Notion")
        return response.json().get('results', [])
    
    except requests.exceptions.ConnectionError:
        logger.error("❌ Connection error: Cannot reach Notion API")
        return []
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout: Notion API request took too long")
        return []
    except Exception as e:
        logger.error(f"❌ Error fetching Notion tasks: {e}")
        return []

def get_todoist_tasks():
    url = 'https://api.todoist.com/api/v1/tasks'
    try:
        response = requests.get(url, headers=todoist_headers, timeout=10)
        
        if response.status_code == 401:
            logger.error("❌ Invalid Todoist API token")
            sys.exit(3)
        
        response.raise_for_status()
        
        data = response.json()
        if isinstance(data, dict) and 'results' in data:
            logger.info(f"✅ Fetched {len(data['results'])} active tasks from Todoist")
            return data['results']
        elif isinstance(data, list):
            logger.info(f"✅ Fetched {len(data)} active tasks from Todoist")
            return data
        else:
            return []
    
    except requests.exceptions.ConnectionError:
        logger.error("❌ Connection error: Cannot reach Todoist API")
        return []
    except Exception as e:
        logger.error(f"❌ Error fetching Todoist tasks: {e}")
        return []

def get_completed_todoist_tasks():
    url = 'https://api.todoist.com/api/v1/tasks'
    params = {'state': 'completed'}
    
    try:
        response = requests.get(url, headers=todoist_headers, params=params, timeout=10)
        
        if response.status_code == 401:
            logger.error("❌ Invalid Todoist API token")
            return []
        
        response.raise_for_status()
        
        data = response.json()
        if isinstance(data, dict) and 'results' in data:
            logger.info(f"✅ Fetched {len(data['results'])} completed tasks from Todoist")
            return data['results']
        elif isinstance(data, list):
            return data
        else:
            return []
    
    except Exception as e:
        logger.error(f"❌ Error fetching completed Todoist tasks: {e}")
        return []

def load_tasks_from_json(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                logger.info(f"✅ Loaded tasks from {file_path}")
                return json.load(file)
        else:
            logger.warning(f"⚠️ {file_path} not found")
            return []
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Error loading tasks: {e}")
        return []

def save_tasks_to_json(tasks, file_path, source="Unknown"):
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(tasks, file, ensure_ascii=False, indent=2, default=str)
        logger.info(f"✅ Saved {len(tasks)} tasks to {file_path} (from {source})")
    except Exception as e:
        logger.error(f"❌ Error saving tasks: {e}")

def create_todoist_task(content, description='', due_date='', labels=None):
    url = 'https://api.todoist.com/api/v1/tasks'
    
    payload = {'content': content}
    if description:
        payload['description'] = description
    if labels:
        payload['labels'] = labels
    if due_date:
        payload['due_date'] = due_date
    
    try:
        response = requests.post(url, headers=todoist_headers, json=payload, timeout=10)
        response.raise_for_status()
        task_id = response.json().get('id')
        logger.info(f"✅ Created Todoist task: {content}")
        return task_id
    except Exception as e:
        logger.error(f"❌ Error creating Todoist task: {e}")
        return None

def update_todoist_task(task_id, content='', description='', due_date='', labels=None):
    url = f'https://api.todoist.com/api/v1/tasks/{task_id}'
    
    payload = {}
    if content:
        payload['content'] = content
    if description:
        payload['description'] = description
    if labels is not None:
        payload['labels'] = labels
    if due_date:
        payload['due_date'] = due_date
    
    try:
        response = requests.post(url, headers=todoist_headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.debug(f"✅ Updated Todoist task {task_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating Todoist task: {e}")
        return False

def close_todoist_task(task_id):
    url = f'https://api.todoist.com/api/v1/tasks/{task_id}/close'
    
    try:
        response = requests.post(url, headers=todoist_headers, timeout=10)
        response.raise_for_status()
        logger.debug(f"✅ Closed Todoist task {task_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error closing Todoist task: {e}")
        return False

def reopen_todoist_task(task_id):
    url = f'https://api.todoist.com/api/v1/tasks/{task_id}/reopen'
    
    try:
        response = requests.post(url, headers=todoist_headers, timeout=10)
        response.raise_for_status()
        logger.debug(f"✅ Reopened Todoist task {task_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error reopening Todoist task: {e}")
        return False

def delete_todoist_task(task_id):
    url = f'https://api.todoist.com/api/v1/tasks/{task_id}'
    
    try:
        response = requests.delete(url, headers=todoist_headers, timeout=10)
        response.raise_for_status()
        logger.info(f"✅ Deleted Todoist task {task_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error deleting Todoist task: {e}")
        return False

def update_notion_task(task_id, properties):
    url = f'https://api.notion.com/v1/pages/{task_id}'
    payload = {'properties': properties}
    
    try:
        response = requests.patch(url, headers=notion_headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.debug(f"✅ Updated Notion task {task_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating Notion task: {e}")
        return False

def delete_notion_task(task_id):
    url = f'https://api.notion.com/v1/pages/{task_id}'
    payload = {'archived': True}
    
    try:
        response = requests.patch(url, headers=notion_headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"✅ Archived Notion task {task_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error deleting Notion task: {e}")
        return False