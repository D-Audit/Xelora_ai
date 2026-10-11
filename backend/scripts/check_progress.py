import requests
import json
import time
import sys

task_id = int(sys.argv[1]) if len(sys.argv) > 1 else 115

while True:
    try:
        resp = requests.get(f'http://127.0.0.1:8000/task/{task_id}/progress')
        data = resp.json()
        print(f"Status: {data['status']}")
        if 'last_action' in data:
            print(f"Last: {data['last_action']}")
        
        if data['status'] in ['completed', 'failed']:
            print(json.dumps(data, indent=2))
            break
        
        time.sleep(2)
    except Exception as e:
        print(f"Error: {e}")
        break
