"""
Async OCR Client for Job-based PDF OCR Processing
Supports async workflow: Upload → Poll Status → Get Result
"""

import requests
import time
from typing import Dict, Any, Optional


class AsyncOCRClient:
    """Client for async job-based OCR API (PDF processing)"""
    
    def __init__(self, base_url: str = "https://catina-cnemial-uninvincibly.ngrok-free.dev", timeout: int = 300):
        """
        Initialize async OCR client
        
        Args:
            base_url: Base URL of the OCR API
            timeout: Maximum time to wait for job completion (seconds)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
    
    def upload_pdf(self, file_path: str) -> str:
        """
        Upload PDF file for OCR processing
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            job_id: Unique identifier for tracking the OCR job
            
        Raises:
            RuntimeError: If upload fails
        """
        upload_url = f"{self.base_url}/ocr/upload"
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                response = self.session.post(upload_url, files=files, timeout=30)
            
            if response.status_code != 200:
                raise RuntimeError(f"Upload failed (HTTP {response.status_code}): {response.text}")
            
            data = response.json()
            job_id = data.get('job_id')
            
            if not job_id:
                raise RuntimeError(f"No job_id in response: {data}")
            
            print(f"✅ PDF uploaded successfully. Job ID: {job_id}")
            return job_id
            
        except Exception as e:
            raise RuntimeError(f"Failed to upload PDF: {e}")
    
    def upload_file_object(self, file_obj, filename: str) -> str:
        """
        Upload file object (from Flask request) for OCR processing
        
        Args:
            file_obj: File object from request.files
            filename: Original filename
            
        Returns:
            job_id: Unique identifier for tracking the OCR job
        """
        upload_url = f"{self.base_url}/ocr/upload"
        
        try:
            files = {'file': (filename, file_obj, 'application/pdf')}
            response = self.session.post(upload_url, files=files, timeout=30)
            
            if response.status_code != 200:
                raise RuntimeError(f"Upload failed (HTTP {response.status_code}): {response.text}")
            
            data = response.json()
            job_id = data.get('job_id')
            
            if not job_id:
                raise RuntimeError(f"No job_id in response: {data}")
            
            print(f"✅ File uploaded successfully. Job ID: {job_id}")
            return job_id
            
        except Exception as e:
            raise RuntimeError(f"Failed to upload file: {e}")
    
    def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get current status of OCR job
        
        Args:
            job_id: Job identifier
            
        Returns:
            Status data including: status, progress, debug_info
        """
        status_url = f"{self.base_url}/ocr/status/{job_id}"
        
        try:
            response = self.session.get(status_url, timeout=10)
            
            if response.status_code != 200:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
            
            return response.json()
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def poll_until_complete(self, job_id: str, interval: int = 5, callback=None) -> str:
        """
        Poll job status until completion or timeout
        
        Args:
            job_id: Job identifier
            interval: Seconds between status checks
            callback: Optional function to call on each status update
            
        Returns:
            Final status ("completed" or "error")
            
        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        start_time = time.time()
        
        while True:
            elapsed = int(time.time() - start_time)
            
            if elapsed > self.timeout:
                raise TimeoutError(f"Job did not complete within {self.timeout}s")
            
            status_data = self.get_status(job_id)
            status = status_data.get('status')
            
            # Call callback if provided
            if callback:
                callback(status_data, elapsed)
            
            # Check terminal states
            if status == 'completed':
                print(f"\n✅ Job completed in {elapsed}s")
                return 'completed'
            
            if status == 'error':
                error_msg = status_data.get('error', 'Unknown error')
                raise RuntimeError(f"OCR job failed: {error_msg}")
            
            # Continue polling
            time.sleep(interval)
    
    def get_result(self, job_id: str) -> str:
        """
        Retrieve OCR result text
        
        Args:
            job_id: Job identifier
            
        Returns:
            Extracted text content
            
        Raises:
            RuntimeError: If result retrieval fails
        """
        result_url = f"{self.base_url}/ocr/result/{job_id}"
        
        try:
            response = self.session.get(result_url, timeout=30)
            
            if response.status_code != 200:
                raise RuntimeError(f"Failed to get result (HTTP {response.status_code}): {response.text}")
            
            data = response.json()
            text_content = data.get('text', '')
            
            return text_content
            
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve result: {e}")
    
    def process_pdf(self, file_path: str, verbose: bool = True) -> str:
        """
        Complete workflow: upload, poll, and get result
        
        Args:
            file_path: Path to PDF file
            verbose: Print progress messages
            
        Returns:
            Extracted OCR text
        """
        # Upload
        job_id = self.upload_pdf(file_path)
        
        # Poll with progress callback
        def progress_callback(status_data, elapsed):
            if not verbose:
                return
            
            status = status_data.get('status', 'unknown')
            debug_logs = status_data.get('debug_info', {}).get('logs', [])
            last_msg = debug_logs[-1]['m'] if debug_logs else "Processing..."
            
            print(f"\r⏳ [{elapsed}s] Status: {status.upper()} | {last_msg[:60]}...", end='')
        
        self.poll_until_complete(job_id, callback=progress_callback)
        
        # Get result
        if verbose:
            print("\n📥 Retrieving result...")
        
        result_text = self.get_result(job_id)
        
        if verbose:
            print(f"✅ OCR complete. Extracted {len(result_text)} characters.")
        
        return result_text


# Standalone test
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Async OCR Client for PDF processing")
    parser.add_argument('--file', type=str, required=True, help='Path to PDF file')
    parser.add_argument('--api-url', type=str, 
                        default="https://catina-cnemial-uninvincibly.ngrok-free.dev",
                        help='OCR API base URL')
    args = parser.parse_args()
    
    client = AsyncOCRClient(base_url=args.api_url)
    result = client.process_pdf(args.file)
    
    # Save result
    output_file = f"ocr_result_{int(time.time())}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"\n💾 Result saved to: {output_file}")
