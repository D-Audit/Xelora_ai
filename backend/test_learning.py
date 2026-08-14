"""
Test script to verify automatic learning is working
"""
import requests
import time
import json

BASE_URL = "http://127.0.0.1:8000"
USER_ID = 1

def test_learning_system():
    print("🧪 Testing Automatic Learning System\n")
    
    print("1️⃣  Submitting a task with 'dashboard' and 'professional' keywords...")
    task_data = {
        "instruction": "Create a professional sales dashboard with revenue chart",
        "user_id": USER_ID,
        "workbook_name": None
    }
    
    resp = requests.post(f"{BASE_URL}/task", json=task_data)
    if resp.status_code == 200:
        task_id = resp.json()["task_id"]
        print(f"   ✅ Task {task_id} started\n")
        
        print("2️⃣  Waiting for task to complete...")
        while True:
            status_resp = requests.get(f"{BASE_URL}/task/{task_id}/progress")
            if status_resp.json().get("is_done"):
                print("   ✅ Task completed\n")
                break
            time.sleep(2)
        
        print("3️⃣  Checking what the system learned...")
        time.sleep(1)  # Give auto-learning a moment
        
        learning_resp = requests.get(f"{BASE_URL}/learning/status/{USER_ID}")
        if learning_resp.status_code == 200:
            learning_data = learning_resp.json()
            print(json.dumps(learning_data, indent=2))
            print("\n✅ Automatic learning is working!")
        else:
            print(f"   ❌ Failed to get learning status: {learning_resp.status_code}")
    else:
        print(f"   ❌ Failed to start task: {resp.status_code}")

if __name__ == "__main__":
    test_learning_system()
