"""Bounded page parameters for clinical list routes."""

from dataclasses import dataclass

from fastapi import HTTPException, status


DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_PAGE = 1000


@dataclass(frozen=True)
class PageWindow:
    number: int
    size: int

    @property
    def offset(self) -> int:
        return (self.number - 1) * self.size


def page_window(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> PageWindow:
    if (
        type(page) is not int or not 1 <= page <= MAX_PAGE
        or type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid clinical list page or page size",
        )
    return PageWindow(page, page_size)
