import logging
from typing import List, Any

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer


logger = logging.getLogger(__name__)


class PDFLoader:

    def __init__(self):
        pass

    async def load(self, file_path: str) -> List[Any]:

        try:
            documents = []

            for page_number, page_layout in enumerate(
                extract_pages(file_path),
                start=1
            ):
                text_parts = []

                for element in page_layout:
                    if isinstance(element, LTTextContainer):
                        text_parts.append(element.get_text())

                text = "".join(text_parts).strip()

                if not text:
                    continue

                document = type(
                    "PDFDocument",
                    (),
                    {
                        "page_content": text,
                        "metadata": {
                            "page_number": page_number
                        },
                        "__str__": lambda self: self.page_content
                    }
                )()

                documents.append(document)

            logger.info(
                f"{len(documents)} pages with text loaded from {file_path}"
            )

            return documents

        except Exception as e:
            logger.error(
                f"PDF loading failed: {e}",
                exc_info=True
            )
            raise


pdf_loader = PDFLoader()
