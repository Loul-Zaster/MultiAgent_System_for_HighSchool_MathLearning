import time
import json
import requests
import argparse
from typing import Optional, Dict, Any

class VinternClient:
    def __init__(self, api_url: str, default_timeout: float = 120.0):
        self.api_url = api_url.rstrip("/")
        self.default_timeout = default_timeout
        self._session = requests.Session()

    def health(self, timeout: float = 10.0) -> Dict[str, Any]:
        r = self._session.get(self.api_url + "/", timeout=timeout)
        r.raise_for_status()
        return r.json()

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repetition_penalty: float = 1.05,
        do_sample: bool = True,
        timeout: Optional[float] = None,
        return_full_json: bool = False,
    ) -> Any:
        """Gửi prompt văn bản tới API /generate"""
        payload = {
            "prompt": prompt,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
            "do_sample": do_sample,
        }
        r = self._session.post(
            self.api_url + "/generate",
            json=payload,
            timeout=timeout or self.default_timeout,
        )
        if not r.ok:
            raise RuntimeError(f"/generate error {r.status_code}: {r.text[:500]}")
        data = r.json()
        return data if return_full_json else data.get("text", "")

    def upload_image(
        self,
        image_path: str,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Upload image to OCR service using /ocr/upload endpoint"""
        with open(image_path, "rb") as f:
            files = {"file": f}
            r = self._session.post(
                self.api_url + "/ocr/upload",
                files=files,
                timeout=timeout or self.default_timeout,
            )
        if not r.ok:
            raise RuntimeError(f"/ocr/upload error {r.status_code}: {r.text[:500]}")
        
        # The new API returns job-based response, so we need to handle it
        data = r.json()
        
        # If it's a job-based response, we need to poll for results
        if "job_id" in data:
            job_id = data["job_id"]
            # Poll for completion
            return self._poll_job_result(job_id, timeout or self.default_timeout)
        
        # Otherwise return as-is (for backward compatibility)
        return data
    
    def _poll_job_result(self, job_id: str, timeout: float) -> Dict[str, Any]:
        """Poll job status until completion"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check status
            status_r = self._session.get(
                self.api_url + f"/ocr/status/{job_id}",
                timeout=10
            )
            
            if not status_r.ok:
                raise RuntimeError(f"Failed to check job status: {status_r.status_code}")
            
            status_data = status_r.json()
            job_status = status_data.get("status")
            
            if job_status == "completed":
                # Get result
                result_r = self._session.get(
                    self.api_url + f"/ocr/result/{job_id}",
                    timeout=10
                )
                
                if not result_r.ok:
                    raise RuntimeError(f"Failed to get result: {result_r.status_code}")
                
                result_data = result_r.json()
                
                # Format to match expected response structure
                return {
                    "status": "ok",
                    "merged_text": result_data.get("text", ""),
                    "blocks": []  # OCR service doesn't return blocks
                }
            
            elif job_status == "error":
                error_msg = status_data.get("error", "Unknown error")
                raise RuntimeError(f"OCR job failed: {error_msg}")
            
            # Still processing, wait and retry
            time.sleep(2)
        
        raise RuntimeError(f"OCR job timeout after {timeout}s")


def wait_until_ready(api_url: str, timeout: float = 30.0, interval: float = 0.5) -> Dict[str, Any]:
    """Chờ API health check lên OK"""
    api_url = api_url.rstrip("/")
    deadline = time.time() + timeout
    last_err: Optional[Exception] = None
    while time.time() < deadline:
        try:
            r = requests.get(api_url + "/", timeout=2.0)
            if r.ok:
                return r.json()
        except Exception as e:
            last_err = e
        time.sleep(interval)
    raise TimeoutError(
        f"Server không sẵn sàng trong {timeout}s. Lỗi cuối: {repr(last_err)}"
    )


def main():
    parser = argparse.ArgumentParser(description="Client test cho Vintern API")
    parser.add_argument("--api-url", type=str,
                        default="https://rational-vocal-piglet.ngrok-free.app",
                        help="URL API ngrok")
    parser.add_argument("--mode", choices=["text", "image"], default="image",
                        help="Chọn mode: hỏi văn bản (text) hoặc upload ảnh (image)")
    parser.add_argument("--prompt", type=str,
                        default=" <image> Đọc công thức toán học trong ảnh và xuất đúng LaTeX. Chỉ trả về nội dung công thức, không cần giải thích thêm.",
                        help="Prompt cho mode text")
    parser.add_argument("--image", type=str,
                        default="/kaggle/working/img_to_latex_diagram.png",
                        help="Đường dẫn ảnh cho mode image")
    args = parser.parse_args()

    client = VinternClient(args.api_url)

    # Đợi server sẵn sàng
    print("Đợi server sẵn sàng...")
    health = wait_until_ready(args.api_url)
    print("Health check:", health)

    if args.mode == "text":
        print("Chế độ TEXT: Gửi prompt...")
        text = client.generate(args.prompt, max_new_tokens=80)
        print("\nKết quả văn bản:\n", text)
    else:
        print("Chế độ IMAGE: Upload ảnh...")
        resp = client.upload_image(args.image)
        print("Raw resp:", resp)

        if resp.get("status") != "ok":
            print("Lỗi upload:", resp.get("msg", resp))
            return  

        print("\nUpload thành công!")

if __name__ == "__main__":
    main()