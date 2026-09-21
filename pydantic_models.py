from typing import Optional, List

from pydantic import BaseModel, Field, HttpUrl


class JobLocation(BaseModel):
    display_name: str
    area: Optional[List[str]] = Field(default_factory=list)


class JobCompany(BaseModel):
    display_name: str


class JobCategory(BaseModel):
    label: Optional[str] = None
    tag: Optional[str] = None


class JobListing(BaseModel):
    """Clean representation of an individual job posting."""

    id: str
    title: str
    company: str
    location: str
    created: str
    description: str
    redirect_url: HttpUrl

    @classmethod
    def from_raw(cls, raw: dict) -> "JobListing":
        """Extracts and normalizes raw Adzuna listing dictionaries."""
        company_name = raw.get("company", {}).get("display_name", "Not Specified")
        location_name = raw.get("location", {}).get("display_name", "Not Specified")

        # Clean URL: strip tracking/query parameters to save tokens
        raw_url = raw.get("redirect_url", "")
        clean_url = raw_url.split("?")[0] if raw_url else raw_url

        return cls(
            id=str(raw.get("id")),
            title=raw.get("title", "Unknown Title"),
            company=company_name,
            location=location_name,
            created=raw.get("created", ""),
            # Truncate summary to avoid blowing out context
            description=raw.get("description", "").strip()[:300],
            redirect_url=clean_url,
        )


class JobSearchResultPayload(BaseModel):
    """Payload to serialize and feed directly to the LLM agent."""

    total_matches: int
    mean_salary: Optional[float] = None
    jobs: List[JobListing]

    @classmethod
    def from_adzuna_response(cls, raw_data: dict) -> "JobSearchResultPayload":
        """Parses the full Adzuna response object into a lean LLM-ready model."""
        raw_results = raw_data.get("results", [])
        clean_jobs = [JobListing.from_raw(item) for item in raw_results]

        return cls(
            total_matches=raw_data.get("count", len(clean_jobs)),
            mean_salary=raw_data.get("mean"),
            jobs=clean_jobs,
        )

    def to_model_json(self) -> str:
        """Returns clean, formatted JSON ready to be passed into the tool message content."""
        return self.model_dump_json(indent=2)