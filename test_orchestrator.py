#!/usr/bin/env python3
"""
Test script for Phase 1 Orchestrator implementation (Status-Based)

This script tests the new status-based workflow:
1. Create a pending todo item
2. Analyze task for AI suitability  
3. If suitable, orchestrator sets status to 'processing' and executes
4. Verify task completion
"""

import asyncio
import httpx
import time
import json
from typing import Dict, Any
from app.config import BASE_URL


class OrchestratorTester:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or BASE_URL
        self.client = httpx.AsyncClient(base_url=self.base_url)
        
    async def test_workflow(self) -> None:
        """Test the complete orchestrator workflow"""
        print("🚀 Testing Phase 1 Orchestrator Workflow (Status-Based)")
        print("=" * 60)
        
        try:
            # Step 1: Create pending task
            print("📝 Step 1: Creating pending task...")
            item_id = await self.create_pending_task()
            print(f"✅ Created task with ID: {item_id}")
            
            # Step 2: Analyze and potentially trigger orchestration
            print("\n🧠 Step 2: Analyzing task for AI suitability...")
            analysis_result = await self.analyze_task(item_id)
            print(f"✅ Analysis result: {analysis_result}")
            
            if analysis_result['orchestration_started']:
                # Step 3: Wait and check completion
                print("\n⏳ Step 3: Waiting for completion...")
                final_status = await self.wait_for_completion(item_id)
                print(f"✅ Final status: {final_status}")
                
                # Step 4: Verify results
                print("\n🔍 Step 4: Verifying results...")
                await self.verify_results(item_id)
                
                print("\n🎉 Test completed successfully!")
            else:
                print(f"\n⚠️ Task was not suitable for AI processing:")
                print(f"   Reason: {analysis_result['reasoning']}")
                print(f"   Confidence: {analysis_result['confidence']:.0%}")
                print("\n🔄 Testing with a more AI-suitable task...")
                await self.test_ai_suitable_task()
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            raise
        finally:
            await self.client.aclose()
    
    async def create_pending_task(self) -> str:
        """Create a new pending task (might not be AI suitable)"""
        task_data = {
            "title": "Buy milk from grocery store",
            "description": "Get 2% milk for the weekend"
        }
        
        response = await self.client.post("/items", json=task_data)
        
        if response.status_code != 200:
            raise Exception(f"Failed to create task: {response.status_code} - {response.text}")
        
        item = response.json()
        return item["id"]
    
    async def analyze_task(self, item_id: str) -> Dict[str, Any]:
        """Analyze task for AI suitability and potentially trigger orchestration"""
        response = await self.client.post(f"/orchestrator/analyze/{item_id}")
        
        if response.status_code != 200:
            raise Exception(f"Failed to analyze task: {response.status_code} - {response.text}")
        
        return response.json()
    
    async def wait_for_completion(self, item_id: str, timeout: int = 30) -> str:
        """Wait for orchestration to complete"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = await self.get_task_status(item_id)
            current_state = status.get("status", "unknown")
            
            print(f"  Current state: {current_state}")
            
            if current_state == "completed":
                return current_state
            elif current_state == "failed":
                raise Exception("Orchestration failed")
            
            await asyncio.sleep(2)  # Wait 2 seconds before checking again
        
        raise Exception("Timeout waiting for completion")
    
    async def get_task_status(self, item_id: str) -> Dict[str, Any]:
        """Get current task status"""
        response = await self.client.get(f"/orchestrator/items/{item_id}/status")
        
        if response.status_code != 200:
            raise Exception(f"Failed to get status: {response.status_code} - {response.text}")
        
        return response.json()
    
    async def verify_results(self, item_id: str) -> None:
        """Verify the results of orchestration"""
        # Get the updated item
        response = await self.client.get(f"/items/{item_id}")
        
        if response.status_code != 200:
            raise Exception(f"Failed to get item: {response.status_code}")
        
        item = response.json()
        
        print(f"  Item state: {item.get('state')}")
        print(f"  AI task: {item.get('is_ai_task')}")
        print(f"  Orchestration status: {item.get('orchestration_status', 'N/A')}")
        
        # Check if description was updated with results
        description = item.get("description", "")
        if "AI Task Result:" in description:
            print("✅ Results were added to item description")
            # Show first 200 chars of results
            result_start = description.find("AI Task Result:")
            if result_start != -1:
                result_snippet = description[result_start:result_start+200]
                print(f"  Results preview: {result_snippet}...")
        else:
            print("⚠️  No results found in description")
        
        # Verify state is completed
        if item.get("state") == "completed":
            print("✅ Item marked as completed")
        else:
            print(f"⚠️  Item state is '{item.get('state')}' instead of 'completed'")
    
    async def test_ai_suitable_task(self) -> None:
        """Test with a task that should be suitable for AI processing"""
        print("\n🔄 Creating AI-suitable research task...")
        
        # Create a research task
        task_data = {
            "title": "Research Python async programming best practices",
            "description": "Find the latest best practices and examples for Python asyncio programming in 2024"
        }
        
        response = await self.client.post("/items", json=task_data)
        if response.status_code != 200:
            print(f"❌ Failed to create AI-suitable task: {response.text}")
            return
        
        item = response.json()
        item_id = item["id"]
        print(f"✅ Created AI-suitable task: {item_id}")
        
        # Analyze it
        print("\n🧠 Analyzing AI-suitable task...")
        analysis = await self.analyze_task(item_id)
        
        print(f"  Task type: {analysis['task_type']}")
        print(f"  Suitable: {analysis['suitable']}")
        print(f"  Confidence: {analysis['confidence']:.0%}")
        print(f"  Reasoning: {analysis['reasoning']}")
        
        if analysis['orchestration_started']:
            print("\n⏳ Waiting for AI task completion...")
            final_status = await self.wait_for_completion(item_id)
            print(f"✅ AI task completed with status: {final_status}")
            
            await self.verify_results(item_id)
            print("\n🎉 AI-suitable task test completed!")
        else:
            print("\n❌ Even the AI-suitable task was not processed")
    
    async def test_batch_analysis(self) -> None:
        """Test batch analysis of multiple tasks"""
        print("\n📦 Testing batch analysis...")
        
        # Create multiple tasks
        tasks = [
            {"title": "Research machine learning frameworks", "description": "Compare TensorFlow vs PyTorch"},
            {"title": "Call mom", "description": "Wish her happy birthday"},
            {"title": "What is the weather like today?", "description": "Check current weather conditions"},
            {"title": "Pick up dry cleaning", "description": "From the shop on Main Street"}
        ]
        
        created_ids = []
        for task in tasks:
            response = await self.client.post("/items", json=task)
            if response.status_code == 200:
                item = response.json()
                created_ids.append(item["id"])
                print(f"  ✅ Created: {task['title']}")
        
        # Run batch analysis
        print(f"\n🔍 Running batch analysis on {len(created_ids)} tasks...")
        response = await self.client.post("/orchestrator/batch-analyze")
        
        if response.status_code == 200:
            results = response.json()
            print(f"📊 Batch analysis results:")
            for result in results:
                status = "🤖" if result['orchestration_started'] else "📝"
                print(f"  {status} {result['task_type']} task - confidence: {result['confidence']:.0%}")
        else:
            print(f"❌ Batch analysis failed: {response.text}")


async def main():
    """Run the orchestrator test"""
    tester = OrchestratorTester()
    await tester.test_workflow()


if __name__ == "__main__":
    print("Phase 1 Orchestrator Test")
    print("Make sure the server is running: uv run uvicorn app.main:app --reload")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        exit(1)