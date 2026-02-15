import json
import logging
from datetime import datetime, timezone, timedelta
from helper import (
    get_todoist_tasks, get_completed_todoist_tasks, get_notion_tasks,
    create_todoist_task, update_todoist_task, load_tasks_from_json, 
    save_tasks_to_json, NOTION_DATABASE_ID, notion_headers
)
import requests
import pytz

logger = logging.getLogger(__name__)

GMT_PLUS_8 = pytz.timezone('Etc/GMT-5')

def create_notion_task_from_todoist(task_name, task_description, task_due_date, todoist_task_id, notion_tasks_id_dict, task_labels):
    if int(todoist_task_id) in notion_tasks_id_dict:
        logger.info(f"ℹ️ Task '{task_name}' already exists in Notion")
        return False

    properties = {
        'Name': {'title': [{'text': {'content': task_name}}]},
        'Done': {'checkbox': False},
        'ID': {'number': int(todoist_task_id)},
        'Type': {'multi_select': [{'name': label} for label in task_labels]}
    }

    if task_due_date:
        try:
            if task_due_date.endswith('Z'):
                due_date_obj = datetime.strptime(task_due_date, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            else:
                due_date_obj = datetime.fromisoformat(task_due_date)
            
            if due_date_obj.tzinfo is None:
                due_date_obj = GMT_PLUS_8.localize(due_date_obj)
            
            formatted_due_date = due_date_obj.astimezone(GMT_PLUS_8).strftime('%Y-%m-%dT%H:%M:%S%z')
            formatted_due_date = formatted_due_date[:-2] + ':' + formatted_due_date[-2:]
            properties['Date'] = {'date': {'start': formatted_due_date}}
        except Exception as e:
            logger.warning(f"⚠️ Could not parse due date for task '{task_name}': {e}")

    try:
        url = 'https://api.notion.com/v1/pages'
        payload = {
            'parent': {'database_id': NOTION_DATABASE_ID},
            'properties': properties
        }
        response = requests.post(url, headers=notion_headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"✅ Created task '{task_name}' in Notion")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating Notion task: {e}")
        return False

def sync_todoist_to_json():
    logger.info("=" * 50)
    logger.info("Starting Todoist to Local/Notion sync...")
    logger.info("=" * 50)
    
    tasks = load_tasks_from_json('tasks.json')
    todoist_tasks = get_todoist_tasks()
    completed_todoist_tasks = get_completed_todoist_tasks()
    notion_tasks = get_notion_tasks()

    tasks_dict = {int(task['todoist-id']): task for task in tasks if task.get('todoist-id')}
    notion_tasks_id_dict = {
        task['properties']['ID']['number']: task 
        for task in notion_tasks 
        if 'ID' in task.get('properties', {}) and 'number' in task['properties']['ID']
    }
    todoist_tasks_dict = {int(task['id']): task for task in todoist_tasks}
    completed_todoist_tasks_dict = {int(task['id']): task for task in completed_todoist_tasks}

    for todoist_task in todoist_tasks:
        task_name = todoist_task.get('content', 'Untitled')
        task_description = todoist_task.get('description', '')
        todoist_task_id = int(todoist_task['id'])
        todoist_task_labels = todoist_task.get('labels', [])
        
        if todoist_task_id not in notion_tasks_id_dict:
            due = todoist_task.get('due')
            task_due_date = due.get('datetime') if due and 'datetime' in due else due.get('date') if due else ''
            
            try:
                create_notion_task_from_todoist(task_name, task_description, task_due_date, todoist_task_id, notion_tasks_id_dict, todoist_task_labels)
            except Exception as e:
                logger.error(f"❌ Error creating Notion task for Todoist task {todoist_task_id}: {e}")

    for task in tasks:
        if not task.get('todoist-id'):
            continue;
            
        todoist_task_id = int(task['todoist-id'])
        task_changed = False

        try:
            if todoist_task_id in completed_todoist_tasks_dict:
                if not task['completed']:
                    task['completed'] = True
                    task_changed = True
                    logger.debug(f"📝 Task marked as completed: {task['name']}")
            
            elif todoist_task_id in todoist_tasks_dict:
                todoist_task = todoist_tasks_dict[todoist_task_id]
                
                if task['completed']:
                    task['completed'] = False
                    task_changed = True
                    logger.debug(f"📝 Task reopened: {task['name']}")
                
                if task['name'] != todoist_task.get('content', ''):
                    task['name'] = todoist_task['content']
                    task_changed = True
                    logger.debug(f"📝 Task name updated: {todoist_task['content']}")
                
                if 'due' in todoist_task and todoist_task['due'] is not None:
                    due = todoist_task['due']
                    due_date = due.get('datetime') if 'datetime' in due else due.get('date', '')
                    
                    if due_date:
                        try:
                            if due_date.endswith('Z'):
                                due_date_obj = datetime.strptime(due_date, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                            else:
                                due_date_obj = datetime.fromisoformat(due_date)
                            
                            if due_date_obj.tzinfo is None:
                                due_date_obj = GMT_PLUS_8.localize(due_date_obj)
                            
                            due_date = due_date_obj.astimezone(GMT_PLUS_8).strftime('%Y-%m-%dT%H:%M:%S%z')
                            due_date = due_date[:-2] + ':' + due_date[-2:]
                            
                            if task['due_date'] != due_date:
                                task['due_date'] = due_date
                                task_changed = True
                        except Exception as e:
                            logger.warning(f"⚠️ Could not parse due date: {e}")
                else:
                    if task.get('due_date') is not None:
                        task['due_date'] = None
                        task_changed = True
                
                if set(task.get('labels', [])) != set(todoist_task.get('labels', [])):
                    task['labels'] = todoist_task.get('labels', [])
                    task_changed = True
            
            if todoist_task_id not in todoist_tasks_dict and todoist_task_id not in completed_todoist_tasks_dict:
                if not task.get('deleted', False):
                    task['deleted'] = True
                    task_changed = True
                    logger.info(f"🗑️ Task marked as deleted: {task['name']}")

            if task_changed:
                task['last_modified'] = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            logger.error(f"❌ Error processing task {todoist_task_id}: {e}")
            continue

    save_tasks_to_json(tasks, 'tasks.json', "Todoist")
    logger.info("✅ Todoist to Local sync completed")

if __name__ == "__main__":
    sync_todoist_to_json()