import re



def extract_terraform(prompt:str):


    if not prompt:

        return None



    # bloc markdown terraform

    match = re.search(

        r"```(?:terraform|hcl)?(.*?)```",

        prompt,

        re.DOTALL

    )


    if match:


        return match.group(1).strip()



    # détection simple HCL

    if (

            "resource" in prompt

            and

            "{" in prompt

    ):


        return prompt



    return None