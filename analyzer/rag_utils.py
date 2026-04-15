import logging
from django.conf import settings
from groq import Groq

logger = logging.getLogger(__name__)

# def rag_pipeline(text: str, query: str = "Summarize this research paper"):
#     """Main fast Groq analysis function used by your views"""
#     try:
#         text = text or ""
#         if len(text.strip()) < 20:
#             return "Not enough content in the document to analyze."

#         client = Groq(api_key=settings.GROQ_API_KEY)

#         # Take beginning + end for better context
#         # context = (text[:25000] + "\n...\n" + text[-15000:]) if len(text) > 40000 else text

#         MAX_CHARS = 12000   # safe limit

#         if len(text) > MAX_CHARS:
#                 context = text[:6000] + "\n...\n" + text[-6000:]
#         else:
#             context = text

#         prompt = f"""
# You are an expert research assistant.

# CONTEXT:
# {context}

# QUESTION:
# {query}

# INSTRUCTIONS:
# - Provide a clear, structured answer.
# - Use bullet points where helpful.
# - If information is not in the context, clearly mention it.
# """

#         response = client.chat.completions.create(
#             model="llama-3.3-70b-versatile",
#             messages=[
#                 {"role": "system", "content": "You are an expert academic research assistant."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.3,
#             max_tokens=2000,
#         )

#         # return response.choices[0].message.content
#         return {
#              "summary": response.choices[0].message.content
#             }
#     except Exception as e:
#         logger.error("GROQ Pipeline Error", exc_info=True)
#         return f"Error analyzing the paper: {str(e)}"

def rag_pipeline(text: str, query: str = "Summarize this research paper"):
    try:
        text = text or ""
        if len(text.strip()) < 20:
            return {"summary": "Not enough content in the document to analyze."}

        client = Groq(api_key=settings.GROQ_API_KEY)

        # ✅ SAFE CONTEXT LIMIT
        MAX_CHARS = 12000
        if len(text) > MAX_CHARS:
            context = text[:6000] + "\n...\n" + text[-6000:]
        else:
            context = text

        prompt = f"""
You are an expert research assistant.

Analyze the research paper and provide:
- Summary
- Key Contributions
- Methodology
- Results
- Limitations

CONTEXT:
{context}
"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert academic research assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500,
        )

        return {
            "summary": response.choices[0].message.content
        }

    except Exception as e:
        logger.error("GROQ Pipeline Error", exc_info=True)
        return {
            "summary": f"Error analyzing the paper: {str(e)}"
        }
def analyze_text_with_groq(text: str, prompt: str = "Summarize this:") -> str:
    """Simple function - kept for compatibility with views.py"""
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"{prompt}\n\n{text}"}],
            temperature=0.7,
            max_tokens=1500,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"analyze_text_with_groq Error: {str(e)}", exc_info=True)
        return f"Error: {str(e)}"