from typing import Optional, Dict, List
from pydantic import BaseModel, Field

# ──────────────────────────────────────────────
# Blueprint Sub-Schemas
# ──────────────────────────────────────────────
class IntegrationMetadata(BaseModel):
    target_system: str = Field(description="Name of the external API/service")
    api_version: str = Field(description="Version from the SOW")

class ServiceClassification(BaseModel):
    priority: str = Field(description="'mandatory' or 'optional'")
    reason: str = Field(description="Why this service is mandatory or optional")

class SecurityConfig(BaseModel):
    auth_type: str = Field(description="Bearer | ApiKey | Basic")
    credential_vault_reference: str = Field(
        description="MUST start with ENV. Never put actual keys here."
    )
    target_url: str = Field(description="Full endpoint URL from the SOW")

class SchemaRules(BaseModel):
    request_mapping: Dict[str, str] = Field(
        description="Dictionary mapping target_field to JSONPath expressions ($.field)"
    )
    response_logic: str = Field(description="Business rule from SOW")

class Blueprint(BaseModel):
    integration_metadata: IntegrationMetadata
    service_classification: ServiceClassification
    security_config: SecurityConfig
    schema_transformation_rules: SchemaRules

# ──────────────────────────────────────────────
# Catalog Entry Sub-Schemas
# ──────────────────────────────────────────────
class TechnicalInterface(BaseModel):
    protocol: str = Field(description="REST | SOAP | GraphQL")
    method: str = Field(description="POST | GET | PUT")
    authentication_methods: List[str] = Field(description="Bearer | ApiKey | OAuth2 | Basic")

class DataSchema(BaseModel):
    mandatory_fields: List[str]
    optional_fields: List[str]
    output_structure: List[str]

class CatalogEntry(BaseModel):
    name: str
    service_name: str = Field(description="lowercase_snake_case config filename")
    version: str
    description: str
    category: str
    provider: str
    supported_actions: List[str]
    credential_reference: str
    target_endpoint: str
    technical_interface: TechnicalInterface
    data_schema: DataSchema
    expected_request_fields: List[str]
    expected_response_fields: List[str]

# ──────────────────────────────────────────────
# Rejection Error Schema
# ──────────────────────────────────────────────
class Rejection(BaseModel):
    reason: str = Field(description="Clear explanation of why SOW cannot be integrated.")
    missing_info: List[str] = Field(description="List of specific missing pieces.")
    suggestion: str = Field(description="What the user should provide to fix this.")

# ──────────────────────────────────────────────
# Final Output Schema used by LangChain
# ──────────────────────────────────────────────
class AgentOutput(BaseModel):
    """The final structured output expected from the LLM."""
    blueprint: Optional[Blueprint] = None
    catalog_entry: Optional[CatalogEntry] = None
    rejection: Optional[Rejection] = None
