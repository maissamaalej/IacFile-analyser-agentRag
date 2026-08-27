import json
import traceback

from app.services.llm_service import llm_service




# ==================================================
# JSON extractor
# ==================================================

def extract_json(text):


    try:

        data = json.loads(text)


        if (
                "grounded" in data
                and "score" in data
        ):

            return data


    except Exception:

        pass



    return None





# ==================================================
# Hallucination evaluation
# ==================================================

async def evaluate_groundedness(

        question,

        documents,

        answer

):


    # IMPORTANT:
    # envoyer seulement les meilleurs chunks

    context = "\n\n".join(

        doc.get(
            "content",
            ""
        )[:1500]


        for doc in documents[:3]

    )



    messages=[


        {


            "role":"system",

            "content":"""

You are a RAG evaluation classifier.

Your ONLY task is to classify if the answer is supported by context.

Return ONLY JSON.

Allowed output:

{
 "grounded": true,
 "score": 0.95
}


Rules:

- true = answer supported by context
- false = unsupported information
- score between 0 and 1
- no explanation
- no markdown
- no extra keys

"""

        },


        {


            "role":"user",

            "content":f"""


Question:

{question}


Context:

{context}


Answer:

{answer}


Return JSON only.

"""

        }


    ]



    try:



        response = await llm_service.generate_judge(

            messages=messages,

            temperature=0,

            max_tokens=100

        )



        print(
            "\n========== RAW JUDGE =========="
        )

        print(response)

        print(
            "================================"
        )



        evaluation = extract_json(
            response
        )



        # Retry

        if evaluation is None:


            print(
                "Retry judge..."
            )


            retry = await llm_service.generate_judge(

                messages=[

                    {

                        "role":"system",

                        "content":"""

Return ONLY:

{
 "grounded": false,
 "score":0
}

"""

                    },


                    {

                        "role":"user",

                        "content":response

                    }

                ],

                temperature=0,

                max_tokens=50

            )



            evaluation = extract_json(
                retry
            )



        if evaluation is None:


            raise Exception(
                "Invalid judge JSON"
            )



        grounded = bool(

            evaluation.get(
                "grounded",
                False
            )

        )



        score = float(

            evaluation.get(
                "score",
                0
            )

        )



        score=max(
            0,
            min(
                score,
                1
            )
        )



        print(
            "\n========== PARSED =========="
        )

        print(evaluation)

        print(
            "============================"
        )



        return {


            "grounded":grounded,


            "score":score


        }




    except Exception as e:



        print(
            "\n========== EVALUATION ERROR =========="
        )


        traceback.print_exc()



        return {


            "grounded":False,


            "score":0,


            "error":str(e)

        }