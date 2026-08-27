from typing import List, Dict, Any


class Chunker:


    MAX_CHARS = 2000



    def split(
            self,
            elements: List[Any],
            source:str
    ) -> List[Dict[str,Any]]:


        chunks=[]

        current_text=[]

        current_title=None

        current_page=None

        chunk_id=0



        for element in elements:


            text = getattr(
                element,
                "text",
                ""
            )


            if not text:
                continue



            category = getattr(
                element,
                "category",
                ""
            )


            page = getattr(
                element.metadata,
                "page_number",
                None
            )



            # garder le titre comme contexte
            if category == "Title":

                current_title=text



            # ajouter tous les contenus
            current_text.append(text)



            current_page = page



            size=len(
                "\n".join(current_text)
            )



            # création chunk
            if size >= self.MAX_CHARS:


                chunks.append({

                    "id":chunk_id,


                    "content":
                        "\n".join(current_text),


                    "metadata":{

                        "source":source,

                        "page":current_page,

                        "title":current_title

                    }

                })


                chunk_id+=1


                current_text=[]



        # dernier morceau

        if current_text:


            chunks.append({

                "id":chunk_id,

                "content":
                    "\n".join(current_text),

                "metadata":{

                    "source":source,

                    "page":current_page,

                    "title":current_title

                }

            })


        return chunks



chunker=Chunker()