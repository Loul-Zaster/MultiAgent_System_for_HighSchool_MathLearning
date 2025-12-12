import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv

# Bổ sung parent directory vào sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from OCR.ocr_model import VinternClient, wait_until_ready
from MCP.notion_mcp_client import NotionMCPClient

# Load biến môi trường
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")

# Đường dẫn chính xác tới mcp_server.py
MCP_SERVER = os.path.join(BASE_DIR, "MCP", "mcp_server.py")


def format_blocks(resp: dict) -> str:
    """
    Format OCR blocks thành Markdown gọn:
    - Text block: ghép các mảnh lại thành một đoạn có câu cú liền mạch
    - Latex block: wrap trong $$ ... $$
    """
    blocks = resp.get("blocks", [])
    if not blocks:
        return resp.get("merged_text", "")

    formatted = []
    for b in blocks:
        text = b.get("text", "").strip()
        btype = b.get("type")
        if not text:
            continue
        if btype == "latex":
            formatted.append(f"$$\n{text}\n$$")
        else:
            # Ghép text OCR: loại bỏ xuống dòng lặt vặt (trừ khi có trắng dòng)
            lines = [line.strip() for line in text.splitlines()]
            # gộp các mẩu chữ rời bằng khoảng trắng, bỏ dòng trống
            joined = " ".join(l for l in lines if l)
            formatted.append(joined)

    # Ghép lại các block, mỗi block cách nhau 2 dòng
    return "\n\n".join(formatted)   


async def write_to_notion(page_id: str, content: str):
    """Ghi nội dung OCR đã format vào Notion page"""
    notion_client = NotionMCPClient(MCP_SERVER, NOTION_TOKEN)
    async with notion_client.connect():
        text_block = f"Kết quả OCR:\n\n{content}"
        await notion_client.update_page(page_id, content=text_block)
        print("Đã ghi OCR vào Notion page:", page_id)


def main():
    parser = argparse.ArgumentParser(description="Chạy OCR và ghi kết quả vào Notion")
    parser.add_argument(
        "--api-url",
        type=str,
        default="https://rational-vocal-piglet.ngrok-free.app",
        help="URL API OCR (ngrok)",
    )
    parser.add_argument(
        "--image", type=str, required=True, help="Đường dẫn tới ảnh cần OCR"
    )
    parser.add_argument(
        "--page", type=str, default='26974e97-008f-80ac-b77d-dbc6a7fe7726', help="ID trang Notion để ghi kết quả"
    )
    args = parser.parse_args()

    client = VinternClient(args.api_url)

    print("Đợi OCR API sẵn sàng…")
    health = wait_until_ready(args.api_url)
    print("Health check:", health)

    # Upload ảnh tới OCR server
    print("Upload ảnh:", args.image)
    resp = client.upload_image(args.image)
    print("Raw resp:", resp)

    if resp.get("status") != "ok":
        print("Lỗi OCR:", resp.get("msg", resp))
        return

    # Lấy text từ blocks → format Markdown gọn
    ocr_text = format_blocks(resp)

    if not ocr_text.strip():
        print("OCR server không trả về text có thể dùng!")
        return

    print("\nKết quả OCR (sau format):\n", ocr_text)

    # Ghi ra Notion
    asyncio.run(write_to_notion(args.page, ocr_text))


if __name__ == "__main__":
    main()