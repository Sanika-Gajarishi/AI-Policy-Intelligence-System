#!/usr/bin/env python3
"""
Automated monitoring script for vector store health
"""
import os
import sys
import json
import time
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.vector_db import load_vector_store
from routes.policies import _load_and_sync_policies

def check_vector_store_health():
    """Comprehensive health check for vector store"""
    health_report = {
        "timestamp": datetime.now().isoformat(),
        "status": "healthy",
        "issues": [],
        "metrics": {}
    }
    
    try:
        # Check vector store exists
        db_path = "data/vector_store"
        if not os.path.exists(db_path):
            health_report["status"] = "error"
            health_report["issues"].append("Vector store directory does not exist")
            return health_report
        
        # Check vector store files
        faiss_file = os.path.join(db_path, "index.faiss")
        pkl_file = os.path.join(db_path, "index.pkl")
        
        if not os.path.exists(faiss_file):
            health_report["issues"].append("FAISS index file missing")
        
        if not os.path.exists(pkl_file):
            health_report["issues"].append("Pickle index file missing")
        
        # Load and test vector store
        db = load_vector_store()
        if db is None:
            health_report["status"] = "error"
            health_report["issues"].append("Failed to load vector store")
            return health_report
        
        # Test search functionality
        try:
            results = db.similarity_search("test query", k=5)
            health_report["metrics"]["search_results"] = len(results)
        except Exception as e:
            health_report["issues"].append(f"Search failed: {str(e)}")
        
        # Check document count
        try:
            all_results = db.similarity_search("renewable energy", k=1000)
            health_report["metrics"]["total_documents"] = len(all_results)
        except Exception as e:
            health_report["issues"].append(f"Document count failed: {str(e)}")
        
        # Check policies vs processed documents
        policies = _load_and_sync_policies()
        health_report["metrics"]["total_policies"] = len(policies)
        
        # Extract unique source files from vector store
        if 'total_documents' in health_report["metrics"]:
            processed_files = set()
            for doc in all_results:
                meta = doc.metadata or {}
                source_file = meta.get('source_file', '')
                if source_file:
                    processed_files.add(source_file)
            
            health_report["metrics"]["processed_files"] = len(processed_files)
            health_report["metrics"]["unprocessed_files"] = len(policies) - len(processed_files)
            
            if health_report["metrics"]["unprocessed_files"] > 0:
                health_report["issues"].append(f"{health_report['metrics']['unprocessed_files']} policies not processed")
        
        # Check file sizes
        if os.path.exists(faiss_file):
            health_report["metrics"]["faiss_size_mb"] = round(os.path.getsize(faiss_file) / (1024*1024), 2)
        
        if os.path.exists(pkl_file):
            health_report["metrics"]["pkl_size_mb"] = round(os.path.getsize(pkl_file) / (1024*1024), 2)
        
        # Determine overall status
        if health_report["issues"]:
            health_report["status"] = "warning" if len(health_report["issues"]) <= 2 else "error"
        
    except Exception as e:
        health_report["status"] = "error"
        health_report["issues"].append(f"Health check failed: {str(e)}")
    
    return health_report

def save_health_report(health_report):
    """Save health report to log file"""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "vector_store_health.log")
    
    with open(log_file, "a") as f:
        f.write(json.dumps(health_report) + "\n")
    
    # Keep only last 100 entries
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        
        if len(lines) > 100:
            with open(log_file, "w") as f:
                f.writelines(lines[-100:])
    except Exception:
        pass

def print_health_summary(health_report):
    """Print formatted health summary"""
    status_emoji = {"healthy": "✅", "warning": "⚠️", "error": "❌"}
    emoji = status_emoji.get(health_report["status"], "❓")
    
    print(f"\n{emoji} Vector Store Health Check - {health_report['timestamp']}")
    print(f"Status: {health_report['status'].upper()}")
    
    if health_report["metrics"]:
        print("\n📊 Metrics:")
        for key, value in health_report["metrics"].items():
            print(f"  {key}: {value}")
    
    if health_report["issues"]:
        print("\n⚠️ Issues:")
        for issue in health_report["issues"]:
            print(f"  - {issue}")
    else:
        print("\n✅ No issues detected")

def main():
    """Main monitoring function"""
    print("Starting vector store health monitoring...")
    
    # Run health check
    health_report = check_vector_store_health()
    
    # Display results
    print_health_summary(health_report)
    
    # Save to log
    save_health_report(health_report)
    
    # Return exit code based on status
    if health_report["status"] == "error":
        return 1
    elif health_report["status"] == "warning":
        return 2
    else:
        return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
