from pydantic import BaseModel
from typing import List, Optional

class TaskRequest(BaseModel):
    task_description: str

class TaskResponse(BaseModel):
    answers: List[str]
    image_uri: Optional[str] = None
