import logging
from typing import List, Any

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer


logger = logging.getLogger(__name__)


class PDFDocument:

    def __init__(self, text: str, page_number: int):
        self.text = text
        self.category = "NarrativeText"
        self.metadata = type(
            "Metadata",
            (),
            {
                "page_number": page_number
            }
        )()

    def __str__(self):
        return self.text


class PDFLoader:

    def __init__(self):
        pass

    async def load(
        self,
        file_path: str
    ) -> List[Any]:

        try:

            documents = []

            for page_number, page_layout in enumerate(
                extract_pages(file_path),
                start=1
            ):

                text_parts = []

                for element in page_layout:

                    if isinstance(element, LTTextContainer):
                        text_parts.append(
                            element.get_text()
                        )

                text = "".join(text_parts).strip()

                if not text:
                    continue

                documents.append(
                    PDFDocument(
                        text=text,
                        page_number=page_number
                    )
                )

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
