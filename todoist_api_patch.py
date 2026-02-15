# todoist_api_patch.py

# This script is designed to handle changes for the Todoist API v1.

import requests

class TodoistAPI:
    def __init__(self, token):
        self.token = token
        self.base_url = 'https://api.todoist.com/rest/v1/'

    def get_tasks(self):
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(f'{self.base_url}tasks', headers=headers)
        return response.json()

    def add_task(self, content):
        headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
        data = {'content': content}
        response = requests.post(f'{self.base_url}tasks', headers=headers, json=data)
        return response.json()

    def update_task(self, task_id, content):
        headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}
        data = {'content': content}
        response = requests.post(f'{self.base_url}tasks/{task_id}', headers=headers, json=data)
        return response.json()

    def delete_task(self, task_id):
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.delete(f'{self.base_url}tasks/{task_id}', headers=headers)
        return response.status_code

# Example usage:
# api = TodoistAPI('your_todoist_api_token')
# tasks = api.get_tasks()  # Get all tasks
# new_task = api.add_task('New task content')  # Add a new task
