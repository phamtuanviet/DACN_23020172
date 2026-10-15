"""HTTP của module reports: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2).
"""

from fastapi import APIRouter

router = APIRouter(tags=["reports"])
