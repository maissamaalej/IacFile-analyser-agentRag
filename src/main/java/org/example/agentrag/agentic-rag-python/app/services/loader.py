import logging
from typing import List, Any

from unstructured.partition.pdf import partition_pdf


logger = logging.getLogger(__name__)


class PDFLoader:


    def __init__(
            self,
            strategy="fast"
    ):
        self.strategy = strategy



    async def load(
            self,
            file_path:str
    ) -> List[Any]:

        try:

            elements = partition_pdf(

                filename=file_path,

                strategy=self.strategy,

                include_page_breaks=True,

                # garde seulement extraction texte
                infer_table_structure=False

            )


            logger.info(
                f"{len(elements)} elements loaded"
            )


            return elements


        except Exception as e:

            logger.error(
                f"PDF loading failed: {e}"
            )

            raise



pdf_loader = PDFLoader()