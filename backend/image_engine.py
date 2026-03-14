from typing import List
from services.ai_service import ai_service


async def generate_images(prompt: str, size: str = "1024x1024", n: int = 1) -> List[str]:
    return await ai_service.generate_image(prompt, size=size, n=n)
