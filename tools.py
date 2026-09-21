from dotenv import load_dotenv

from pydantic_models import JobSearchResultPayload

load_dotenv()

import json
import os
import requests


def get_job_details(
    country_code: str, page_no: int, results_per_page: int, title: str
) -> str:
    """Retrieves job postings from the Adzuna Search API.

    Constructs and sends an authenticated HTTP GET request to the Adzuna Jobs
    endpoint using credentials and base URLs loaded from environment variables.
    Returns the parsed results or formatted error details as a JSON string.

    Environment Variables:
        ADZUNA_BASE_URL (str): The root API URL (e.g., 'https://api.adzuna.com/v1/api/').
        ADZUNA_APPLICATION_ID (str): The Adzuna registered application ID.
        ADZUNA_APPLICATION_KEY (str): The Adzuna secret application API key.

    Args:
        country_code (str): Two-letter ISO country code for the job search
            market (e.g., 'gb', 'us', 'in').
        page_no (int): The page number of results to fetch (starts at 1).
        results_per_page (int): Maximum number of job postings to return per page.
        title (str): Job role or keyword query to search for (maps to the 'what' parameter).

    Returns:
        str: A pretty-printed JSON-formatted string containing:
            - On success (HTTP 200): A dictionary with search metadata and a list of job objects.
            - On HTTP failure: `{"Error": "<response_text>"}`.
            - On network/system exception: `{"Error": "<exception_message>"}`.

    Example:
        >>> jobs_json = get_job_details("us", 1, 10, "Software Engineer")
        >>> data = json.loads(jobs_json)
        >>> if "results" in data:
        ...     print(f"Found {len(data['results'])} jobs.")
    """
    base_url = os.getenv("ADZUNA_BASE_URL", "").rstrip("/")
    app_id = os.getenv("ADZUNA_APPLICATION_ID")
    app_key = os.getenv("ADZUNA_APPLICATION_KEY")

    url = (
        f"{base_url}/jobs/"
        f"{country_code}/search/"
        f"{page_no}?app_id="
        f"{app_id}&app_key="
        f"{app_key}&results_per_page="
        f"{results_per_page}&what="
        f"{title}&content-type=application/json"
    )

    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return json.dumps(JobSearchResultPayload.from_adzuna_response(res.json()).to_model_json(), indent=2)
        else:
            return json.dumps({"Error": res.text}, indent=2)
    except Exception as e:
        return json.dumps({"Error": str(e)}, indent=2)


print(get_job_details("in", 1, 5, 'data science'))